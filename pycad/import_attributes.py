"""Import-only attribute aliases; native authoring keeps strict unique tags.

External blocks can repeat ATTDEF/ATTRIB tags. Match them case-insensitively by
occurrence, reserve real names before generating aliases, and never collapse
repeated instance values into a dict comprehension. Original bytes remain in
the source archive; warnings disclose the changed import-copy names.
"""
from collections import defaultdict

class AttributeTags:
    def __init__(self,tags):
        from .validation import name
        self.original=list(tags)
        for tag in self.original:name(tag,'Attribute tag')
        self.reserved={tag.casefold() for tag in self.original};self.used=set();self.aliases=[];self.by_tag=defaultdict(list);self.renamed=[]
        for tag in self.original:
            alias=tag if tag.casefold() not in self.used else self.unique(tag,self.reserved|self.used)
            self.used.add(alias.casefold());self.aliases.append(alias);self.by_tag[tag.casefold()].append(alias)
            if alias!=tag:self.renamed.append((tag,alias))
    @staticmethod
    def unique(tag,occupied):
        index=2
        while True:
            suffix='__'+str(index);candidate=tag[:255-len(suffix)]+suffix
            if candidate.casefold() not in occupied:return candidate
            index+=1
    def values(self,pairs):
        pairs=list(pairs);reserved=self.used|{tag.casefold() for tag,value in pairs};used=set();counts=defaultdict(int);out={};changed=[]
        for tag,value in pairs:
            from .validation import name
            name(tag,'Attribute tag');fold=tag.casefold();index=counts[fold];counts[fold]+=1;aliases=self.by_tag.get(fold,[])
            if index<len(aliases):alias=aliases[index]
            elif index==0 and fold not in used and fold not in self.used:alias=tag
            else:alias=self.unique(tag,reserved|used)
            # An orphan source tag can equal a generated definition alias.
            # Preserve both values rather than overwrite the earlier entry.
            if alias.casefold() in used:alias=self.unique(tag,reserved|used)
            used.add(alias.casefold());reserved.add(alias.casefold());out[alias]=value
            if alias!=tag:changed.append((tag,alias))
        return out,changed
