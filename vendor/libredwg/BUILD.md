# LibreDWG 0.14 distribution and rebuild

The unmodified corresponding source is `libredwg-0.14.tar.xz` beside this file.
Its SHA-256 is `62ebb73b984f865960f20ed26619ea5f8789d5e3fd088fa40a2598384da81275`.
GNU GPL version 3 or later, AUTHORS and upstream installation instructions are
included. No PY.cad-specific changes were made to LibreDWG source.

Windows x64: the four shipped files are unchanged members of the official
`libredwg-0.14-win64.zip`, SHA-256
`1ad7e15344d20b3426c3435b078d82fb84b35062815946b2cca9c5fc9810fea8`.
See `manifest.json` for each file hash. The upstream ZIP's optional Python,
iconv and PCRE binaries are not included. For a Windows rebuild use the supplied
source's INSTALL/README MSYS2/MinGW instructions, configure for x86_64-w64-mingw32
with bindings/docs disabled, and build dwg2dxf, dwgread, dwgwrite plus libredwg. This reproduces the
reader functionality; bit-identical upstream Windows binaries are not claimed.
Official release: https://github.com/LibreDWG/libredwg/releases/tag/0.14

Linux x64: built on Ubuntu 24.04 with GCC 13.3, GNU make and pkgconf.
The bundled ELF uses glibc 2.38 or later. Older Linux systems should build the
reader locally against their libc and configure PYCAD_DWG_CONVERTER. Extract the
source, then run:

```sh
./configure --disable-shared --enable-static --disable-bindings --disable-docs --enable-release
make -j2 -C src
make -j2 -C programs dwg2dxf dwgread dwgwrite
strip programs/dwg2dxf programs/dwgread programs/dwgwrite
```

Only LibreDWG is statically linked. The host's glibc/libm remain dynamic system
dependencies. On macOS or another architecture build the same CLI for that
system (or install LibreDWG from the system package manager) and place dwg2dxf
on PATH, or set PYCAD_DWG_CONVERTER to its absolute path. Windows and Linux x64
have bundled readers; no macOS binary is bundled in this release.

The binary hash manifest must be updated when rebuilding shipped binaries. Keep
corresponding source, license and notices with any redistributed reader.


16.24 adds `dwgread` and `dwgwrite`. Windows binaries are unchanged members of the same verified official archive, using the existing bundled libredwg-0.dll and Windows system CRT. Linux added tools were built on Ubuntu 24.04 / GCC 13.3 with `./configure PKG_CONFIG=/bin/true --disable-shared --disable-bindings --disable-docs --enable-release`, then `make -j4` and strip. The pkg-config override disables optional package discovery in this build environment; no source changes were made. Both added ELF tools require at most glibc 2.38, link LibreDWG statically, and use system libc/libm. The existing compatibility reader is retained unchanged. All shipped executable hashes are in manifest.json.
