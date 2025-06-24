"""Syntactic sugar:

from sugar import *

imap(lambda x:x+2, [2, 3, 4])
Out[462]: [4, 5, 6]

'a, b, c'-spl
Out[475]: ['a', 'b', 'c']

'a b c'-spls
Out[475]: ['a', 'b', 'c']

'''a
b
c
'''-splnl
Out[475]: ['a', 'b', 'c']

'a>b>c'-splon('>')
Out[487]: ['a', 'b', 'c']

'a b c'-spls-first
Out[481]: 'a'

'a b c'-spls-last
Out[482]: 'c'

'a:x, b:y, c:z'-spld
Out[478]: {'a': 'x', 'b': 'y', 'c': 'z'}

'a:x, b:y, c:z'-spld-flipDict
Out[492]: {'x': 'a', 'y': 'b', 'z': 'c'}

for i, j in 'a:x, b:y, c:z'-spldi:
	print(i+j)
ax
by
cz

'a==1, b==2'-spland
Out[490]: '(a==1)&(b==2)'

df = pd.DataFrame({'x':'a, a, b'-spl, 'y':'c, d, d'-spl, 'z':[1, 2, 3]}); isUnique(df)
Out[473]: True

isUnique(pd.DataFrame({'x':'a, a, b, b'-spl, 'y':'c, d, d, d'-spl}))
Out[474]: False

qselect(df,'y, colX:x')
Out[500]:
   y colX
0  c    a
1  d    a
2  d    b

frontCols(df, 'y, z')
Out[503]:
   y  z  x
0  c  1  a
1  d  2  a
2  d  3  b

"""



import re
import pandas as pd
# import oyaml as yaml  # conda install oyaml # was used for old Obj print
import copy
import more_itertools  # conda install more-itertools

dbg = breakpoint

#various helper functions
timap = lambda *x: tuple(map(*x))
imap = lambda *x: list(map(*x))
izip = lambda *x: list(zip(*x))
ifilter = lambda *x: list(filter(*x))
flatten = lambda x: list(more_itertools.flatten(x))
unique = lambda x: list(set(x))
def dmap(f, d):
    return dict(zip(d, map(f, d.values() if isinstance(d, dict) else d)))

def dfilter(f, d):
    return list(filter(lambda x:f(d[x]), d.keys()))

def dict2df(d, cols = 'k, v'):
    return pd.DataFrame(zip(*[d.keys(), d.values()]), columns = cols-spl)

isUnique=lambda x: x.drop_duplicates().shape == x.shape

def fraise(x):
    raise x if isinstance(x,BaseException) else Exception(x)

#syntactic sugar: Subtract Function Wrapper; f(x) <=> x-F <=> F-x, with F = SFW(f)
class SFW(object):
    def __init__(self, f):
        self.f=f
        self.__doc__ = f.__doc__
    def __call__(self, *x):
        return self.f(*x)
SFW.__matmul__=SFW.__rmatmul__=SFW.__sub__=SFW.__rsub__=SFW.__rrshift__=SFW.__call__

# some code I found on stackexchange, deals with nested brackets and commas inside them
def smartSplit(s, char=',', quotes="'\"", ignoreFirstEmptyString = False):
    def srchrepl(srch, repl, string, quotes):
        """Replace non-bracketed/quoted occurrences of srch with repl in string"""
        resrchrepl = re.compile(r"""(?P<lbrkt>[([{])|(?P<quote>["""+quotes+"""])|(?P<sep>["""
                                + srch + r"""])|(?P<rbrkt>[)\]}])""")
        return resrchrepl.sub(_subfact(repl), string)
    def _subfact(repl):
        """Replacement function factory for regex sub method in srchrepl."""
        level = 0
        qtflags = 0
        def subf(mo):
            nonlocal level, qtflags
            sepfound = mo.group('sep')
            if  sepfound:
                if level == 0 and qtflags == 0:
                    return repl
                else:
                    return mo.group(0)
            elif mo.group('lbrkt'):
                level += 1
                return mo.group(0)
            elif mo.group('quote') == "'":
                qtflags ^= 1            # toggle bit 1
                return "'"
            elif mo.group('quote') == '"':
                qtflags ^= 2            # toggle bit 2
                return '"'
            elif mo.group('rbrkt'):
                level -= 1
                return mo.group(0)
        return subf
    GRPSEP = chr(29)
    r=imap(str.strip, srchrepl(char, GRPSEP, s, quotes).split(GRPSEP))
    if r[-1] == '':
        r=r[:-1]
    if ignoreFirstEmptyString and len(r) > 1 and r[0] == '':
        r = r[1:]
    return r
# quick splits: split-on(character)
splon=lambda c, *args, **kw: SFW(lambda x:smartSplit(x, c, *args, **kw))
# hard-wired character splits
spl=splon(',')
spls=splon(' ')
splnl=splon('\n', ignoreFirstEmptyString = True)
#split dict a, b:c, d:e ...
spld=SFW(lambda x:dict(imap(lambda x:imap(str.strip,(lambda x: x*2 if len(x)==1 else x)(smartSplit(x, ':'))),smartSplit(x))))
#split dict a \n b:c \n d:e ...
spldnl=SFW(lambda x:dict(imap(lambda x:imap(str.strip,(lambda x: x*2 if len(x)==1 else x)(smartSplit(x, ':'))),smartSplit(x,'\n', ignoreFirstEmptyString = True))))
to=lambda y: SFW(lambda x: -1+y/x)
relto=lambda y: SFW(lambda x: -1+x/y)
#split dict a, b=c, d=e, e.g.:
# 'type=hp_month,shTL=0,mTL=0,Nts=40'-spldeq
# {'type': 'hp_month', 'shTL': '0', 'mTL': '0', 'Nts': '40'}
spldeq=SFW(lambda x:dict(imap(lambda x:imap(str.strip,(lambda x: x*2 if len(x)==1 else x)(smartSplit(x, '='))),smartSplit(x))))
#split dict then .items()
spldi=SFW(lambda x: spld.f(x).items())
# deprecated
spland=SFW(lambda x:'&'.join(imap(lambda x:f'({x})', smartSplit(x))))
def _efirst(x):
    if len(x) == 0:
        return '' if type(x) == str else None
    if issubclass(x.__class__,pd.DataFrame):
        return x.iloc[0]
    for i in x:
        return i
def _first(x):
    if issubclass(x.__class__,pd.DataFrame) or issubclass(x.__class__,pd.Series):
        return x.iloc[0]
    return next(iter(x))
def _last(x):
    if issubclass(x.__class__,pd.DataFrame) or issubclass(x.__class__,pd.Series):
        return x.iloc[-1]
    return next(reversed(x))
first=SFW(_first)
last=SFW(_last)
efirst=SFW(_efirst) # handles empty dataframes
# flips keys and values
flipDict = SFW(lambda a: dict((v,k) for k,v in a.items()))

@SFW
def head(x):
    try:
        return x.head()
    except:
        return pd.DataFrame({k: v[:5] for k, v in x.items()})

@SFW
def fapply(s):
    '''syntactic sugar that replaces
def f(x):
    d = {}
    d['v'] = x.v.sum()
    d['dv'] = (x.v*x.c).sum()
    return pd.Series(d, index='v, dv'-spl)

rawData.groupby('s').apply(f)

with

rawData.groupby('s').apply('v: x.v.sum(), dv: (x.v*x.c).sum()'-fapply)'''
    d = dmap(lambda x:compile(x,'<string>','eval'),s-spld)
    def f(x):
        scope = globals(), locals()
        return pd.Series({k:eval(v, *scope) for k, v in d.items()}, index=d.keys())
    return f

@SFW
def qselect(*x):
    '''q-style select/rename columns
    qselect( myTable, 'col, newColName: oldColName, ...')'''
    if len(x) == 2:
        x, s = x
        if len(x.columns)==0:
            return x
        d=s-spld
        return (x[list(d.values())].rename(columns=d-flipDict) if type(x)==pd.DataFrame else x[list(d.values())].rename(d-flipDict))
    else:
        return SFW(lambda y: qselect(y,x[0]))
@SFW
def rename(*x):
    if len(x) == 2:
        x, s = x
        if type(s)==str:
            s = s-spl
        return x.rename(columns={old:new for old, new in zip(list(x.columns)[:len(s)], s)})
    else:
        return SFW(lambda y: rename(y,x[0]))
# General loader utils
def makeColGeneral(t):
    '''Converts mixed-type columns to string as required to save as parquet'''
    for c in t.columns:
        s = set(t[c].map(type))
        if len(s)>1:
            t[c] = t[c].astype(str)
    return t

class FriendlyDataClass(object):
    '''Parent data-container class; defines `self[]` and `x in self`'''
    @property
    def tables(self):
        '''List local variables'''
        return sorted(list(vars(self).keys()))
    def __getitem__(self, x):
        return getattr(self, x)
    def __setitem__(self, x, v):
        return setattr(self, x, v)
    def __contains__(self, x):
        return x in list(vars(self).keys())

def frontCols(x, c):
    '''Moves columns c to the front, similar to q's xcols'''
    if(type(c)==str):
        c = c-spl
    newCols = [i for i in c if i in x.columns] + [i for i in x.columns if not i in c]
    return x[newCols]

class Obj(dict):
    def __init__(self, *args, **kwargs):
        if len(args) == 0 and len(kwargs) == 0:
            args = [{}]
        super().__init__(*args, **kwargs)
        self.__dict__ = self
    def __getitem__(self, k):
        if type(k) == list:
            return [self[i] for i in k]
        else:
            return super().__getitem__(k)

# class Obj0:
#     def __init__(self, **d):
#         object.__setattr__(self, '_dictKeys', list(d.keys()))
#         for a, b in d.items(): object.__setattr__(self, a, b)
#     def __contains__(self, x):
#         return x in self._dictKeys
#     def __len__(self):
#         return len(self._dictKeys)
#     def __getitem__(self, key):
#         return getattr(self, key)
#     def get(self, key, default = None):
#         return self[key] if key in self._dictKeys or default is None else default
#     def _to_dict(self):
#         return {k: getattr(self, k) for k in self._dictKeys}
#     def __iter__(self):
#         for k in self._dictKeys:
#             yield k, getattr(self, k)
#     def __repr__(self):
#         try:
#             r = yaml.dump(self._to_dict())
#         except:
#             r = self._to_dict().__repr__()
#         return r
#     def __setitem__(self, key, value):
#         object.__setattr__(self, key, value)
#         if key not in self._dictKeys:
#             self._dictKeys.append(key)
# Obj0.__setattr__ = Obj0.__setitem__    

# class Obj(Obj0):
#     def __init__(self, **d):
#         Obj0.__init__(self, **d)
#         object.__setattr__(self, 'strict', False)
#         for a, b in d.items():
#             if isinstance(b, (list, tuple)):
#                setattr(self, a, [Obj(**x) if isinstance(x, dict) else x for x in b])
#             else:
#                setattr(self, a, Obj(**b) if isinstance(b, dict) else b)
#     def _to_dict(self):
#         return {k: (lambda x: [y._to_dict() if isinstance(y, Obj) else y for y in x] if type(x)==list else x._to_dict() if isinstance(x, Obj) else x)(getattr(self, k)) for k in self._dictKeys}
#     def __lshift__(self, d):
#         newObj = self.copy()
#         newObj <<= d
#         return newObj
#     def __ilshift__(self, d):
#         if isinstance(d, Obj):
#             self.__ilshift__(d._to_dict())
#         else:
#             for a, b in d.items():
#                 if isinstance(b, (list, tuple)):
#                    setattr(self, a, [Obj(**x) if isinstance(x, dict) else x for x in b])
#                 else:
#                     if isinstance(b, dict):
#                         if a in self._dictKeys and isinstance(getattr(self, a), Obj):
#                             getattr(self, a).__ilshift__(b)
#                         else:
#                             setattr(self, a, Obj(**b) if isinstance(b, dict) else b)
#                     else:
#                         setattr(self, a, b)
#                 if a not in self._dictKeys:
#                     self._dictKeys.append(a)
#         return self
#     def __setattr__(self, key, value):
#         if key not in self._dictKeys:
#             if self._strict:
#                 raise BaseException("Can't add new key, Obj in strict mode")
#             else:
#                 self._dictKeys.append(key)
#         object.__setattr__(self, key, value)
#     def setStrict(self, val):
#         object.__setattr__(self, '_strict', val)
#         for k in self._dictKeys:
#             if type(k) == Obj:
#                 self[k].setStrict(val)
#     def __setitem__(self, key, value):
#         setattr(self, key, value)
#     def copy(self):
#         return copy.deepcopy(self)

# def createNestedObj(*args, init = []):
#     r = copy.deepcopy(init)
#     for a in args[::-1]:
#         r = {i:copy.deepcopy(r) for i in a-spl}
#     return Obj(**r)



def createNestedStruct(*args, init = []):
    r = copy.deepcopy(init)
    for a in args[::-1]:
        if type(a) == str:
            r = {i:copy.deepcopy(r) for i in a-spl}
        elif type(a) in (tuple, list, range):
            r = {i:copy.deepcopy(r) for i in a}
        else:
            r = [copy.deepcopy(r) for i in range(a)]
    return r

runpy = "lambda x:exec(open(x).read())"
# Usage: eval(runpy)('script.py') to run script in current namespace
# Claude AI suggests this instead of runpy:
# def get_main_scope_function():
#     main_module = sys.modules['__main__']
#     main_globals = main_module.__dict__
#     return eval("lambda x: exec(open(x).read())", main_globals)

import pickle
def loadpkl(f):
    return pickle.load(open(f, 'rb'))

def savepkl(x, f):
    pickle.dump(x, open(f, 'wb'))
