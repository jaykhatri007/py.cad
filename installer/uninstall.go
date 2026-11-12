package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

const uninstallManifestName = "uninstall-manifest.json"
const uninstallExeName = "Uninstall-PY.cad.exe"

type uninstallInventory struct {
	Format        int
	Product, Root string
	Files         map[string]string
}

var uninstallDirs = []string{"releases", "python", "cache", "tools", "launchers", "icons"}

func preservedDrawing(name string) bool {
	switch strings.ToLower(filepath.Ext(name)) {
	case ".pycad", ".pycadt", ".dxf", ".dwg", ".dwt", ".pdf", ".ifc", ".step", ".stp", ".iges", ".igs", ".stl", ".obj", ".3mf", ".glb", ".gltf", ".blend", ".bak":
		return true
	}
	return false
}

func uninstallPathAllowed(rel string) bool {
	if rel == "current.json" || rel == uninstallExeName {
		return true
	}
	for _, dir := range uninstallDirs {
		if strings.HasPrefix(rel, dir+"/") && !preservedDrawing(rel) {
			return true
		}
	}
	return false
}

// Validate every ancestor without following links/junctions. Never traverse a
// root or component replaced by a Windows reparse point.
func checkedUninstallPath(root, rel string) (string, error) {
	if !filepath.IsAbs(root) || filepath.Clean(root) != root {
		return "", errors.New("Invalid uninstall root")
	}
	if rel != "" && (strings.ContainsAny(rel, "\\:\x00") || strings.HasPrefix(rel, "/") || filepath.ToSlash(filepath.Clean(filepath.FromSlash(rel))) != rel || rel == ".." || strings.HasPrefix(rel, "../")) {
		return "", errors.New("Unsafe uninstall inventory path")
	}
	path := root
	parts := []string{}
	if rel != "" {
		parts = strings.Split(rel, "/")
	}
	for i := -1; i < len(parts); i++ {
		if i >= 0 {
			path = filepath.Join(path, parts[i])
		}
		info, err := os.Lstat(path)
		if os.IsNotExist(err) {
			return filepath.Join(root, filepath.FromSlash(rel)), nil
		}
		if err != nil {
			return "", err
		}
		if isUninstallLink(info) {
			return "", errors.New("Uninstall refuses symbolic links or reparse points: " + path)
		}
		if i < len(parts)-1 && !info.IsDir() {
			return "", errors.New("Uninstall parent is not a directory")
		}
	}
	return path, nil
}

func uninstallFiles(root string) (map[string]bool, error) {
	if _, err := checkedUninstallPath(root, ""); err != nil {
		return nil, err
	}
	files := map[string]bool{}
	for _, dir := range uninstallDirs {
		path, err := checkedUninstallPath(root, dir)
		if err != nil {
			return nil, err
		}
		if err = filepath.WalkDir(path, func(p string, entry fs.DirEntry, err error) error {
			if os.IsNotExist(err) {
				return nil
			}
			if err != nil {
				return err
			}
			info, err := entry.Info()
			if err != nil {
				return err
			}
			if isUninstallLink(info) {
				if entry.IsDir() {
					return filepath.SkipDir
				}
				return nil
			}
			if !info.Mode().IsRegular() {
				return nil
			}
			rel, err := filepath.Rel(root, p)
			if err != nil {
				return err
			}
			rel = filepath.ToSlash(rel)
			if uninstallPathAllowed(rel) {
				files[rel] = true
			}
			return nil
		}); err != nil {
			return nil, err
		}
	}
	for _, rel := range []string{"current.json", uninstallExeName} {
		if info, err := os.Lstat(filepath.Join(root, rel)); err == nil && info.Mode().IsRegular() && !isUninstallLink(info) {
			files[rel] = true
		}
	}
	return files, nil
}

func uninstallBaseline(root string) (map[string]bool, error) { return uninstallFiles(root) }

func uninstallHash(file string) (string, error) {
	f, err := os.Open(file)
	if err != nil {
		return "", err
	}
	defer f.Close()
	hash := sha256.New()
	if _, err = io.Copy(hash, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(hash.Sum(nil)), nil
}

func loadUninstallInventory(root string) (uninstallInventory, error) {
	var v uninstallInventory
	path, err := checkedUninstallPath(root, uninstallManifestName)
	if err != nil {
		return v, err
	}
	f, err := os.Open(path)
	if err != nil {
		return v, err
	}
	defer f.Close()
	if err = json.NewDecoder(io.LimitReader(f, 64<<20)).Decode(&v); err != nil {
		return v, err
	}
	if v.Format != 1 || v.Product != "PY.cad managed installation" || !strings.EqualFold(v.Root, root) || len(v.Files) == 0 {
		return v, errors.New("This folder has no valid PY.cad uninstall inventory; no files were removed")
	}
	// Validate the complete plan before deleting any file.
	for rel, digest := range v.Files {
		if !uninstallPathAllowed(rel) || len(digest) != 64 {
			return v, errors.New("Invalid uninstall inventory entry")
		}
		if _, err = hex.DecodeString(digest); err != nil {
			return v, err
		}
		if _, err = checkedUninstallPath(root, rel); err != nil {
			return v, err
		}
	}
	return v, nil
}

func saveUninstallInventory(ctx context.Context, root string, before map[string]bool) error {
	old, err := loadUninstallInventory(root)
	if err != nil && !os.IsNotExist(err) {
		return err
	}
	if old.Files == nil {
		old = uninstallInventory{1, "PY.cad managed installation", root, map[string]string{}}
	}
	files, err := uninstallFiles(root)
	if err != nil {
		return err
	}
	for rel := range files {
		if err = ctx.Err(); err != nil {
			return err
		}
		// Existing untracked files are never claimed during an upgrade. Retain
		// prior hashes so later user modifications are preserved on uninstall.
		if before[rel] && rel != "current.json" && rel != uninstallExeName {
			continue
		}
		digest, e := uninstallHash(filepath.Join(root, filepath.FromSlash(rel)))
		if e != nil {
			return e
		}
		old.Files[rel] = digest
	}
	return writeJSON(filepath.Join(root, uninstallManifestName), old)
}

type uninstallResult struct{ Removed, Kept int }

// Only files whose recorded content still matches are removed. Unknown and
// changed files survive, as do drawing formats and files outside this root.
func removeOwnedFiles(ctx context.Context, root string, inventory uninstallInventory, s *progress) (uninstallResult, error) {
	var result uninstallResult
	keys := make([]string, 0, len(inventory.Files))
	for rel := range inventory.Files {
		if rel != uninstallExeName {
			keys = append(keys, rel)
		}
	}
	sort.Strings(keys)
	for i, rel := range keys {
		if err := ctx.Err(); err != nil {
			return result, err
		}
		path, err := checkedUninstallPath(root, rel)
		if err != nil {
			return result, err
		}
		hash, err := uninstallHash(path)
		if os.IsNotExist(err) {
			continue
		}
		if err != nil {
			return result, fmt.Errorf("Close PY.cad and retry removing %s: %w", rel, err)
		}
		if hash != inventory.Files[rel] {
			result.Kept++
			continue
		}
		if err = os.Remove(path); err != nil {
			return result, fmt.Errorf("Close PY.cad and retry removing %s: %w", rel, err)
		}
		result.Removed++
		if s != nil && i%300 == 0 {
			s.note(fmt.Sprintf("Removed %d managed files; preserved %d modified files", result.Removed, result.Kept))
		}
	}
	return result, nil
}

// Remove empty directories only. No RemoveAll call is permitted on an install
// tree, so new drawings and other untracked files cannot be swept up.
func pruneUninstallDirs(root string) {
	dirs := []string{}
	for _, dir := range uninstallDirs {
		path, err := checkedUninstallPath(root, dir)
		if err != nil {
			continue
		}
		_ = filepath.WalkDir(path, func(p string, e fs.DirEntry, err error) error {
			if err != nil {
				return nil
			}
			info, err := e.Info()
			if err != nil {
				return nil
			}
			if isUninstallLink(info) {
				if e.IsDir() {
					return filepath.SkipDir
				}
				return nil
			}
			if e.IsDir() {
				dirs = append(dirs, p)
			}
			return nil
		})
	}
	sort.Slice(dirs, func(i, j int) bool { return len(dirs[i]) > len(dirs[j]) })
	for _, dir := range dirs {
		_ = os.Remove(dir)
	}
}
