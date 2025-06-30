from .qpython_compat import qtype

def parse(q, expr):
    """
    Parse a q expression and return a human-readable representation
    
    Args:
        q: Query function to execute q code  
        expr: Expression to parse
    Returns:
        String representation of the parsed expression
    """
    query = """{[expr]
    f: asc `abs`cor`ej`gtime`like`mins`prev`scov`system`wavg`acos`cos`ema`hclose`lj`ljf`mmax`prior`sdev`tables`where`aj`aj0`count`enlist`hcount`load`mmin`rand`select`tan`while`ajf`ajf0`cov`eval`hdel`log`mmu`rank`set`til`within`all`cross`except`hopen`lower`mod`ratios`setenv`trim`wj`wj1`and`csv`exec`hsym`lsq`msum`raze`show`type`wsum`any`cut`exit`iasc`ltime`neg`read0`signum`uj`ujf`xasc`asc`delete`exp`idesc`ltrim`next`read1`sin`ungroup`xbar`asin`deltas`fby`if`mavg`not`reciprocal`sqrt`union`xcol`asof`desc`fills`ij`ijf`max`null`reval`ss`update`xcols`atan`dev`first`in`maxs`or`reverse`ssr`upper`xdesc`attr`differ`fkeys`insert`mcount`over`rload`string`upsert`xexp`avg`distinct`flip`inter`md5`parse`rotate`sublist`value`xgroup`avgs`div`floor`inv`mdev`peach`rsave`sum`var`xkey`bin`binr`do`get`key`med`pj`rtrim`sums`view`xlog`ceiling`dsave`getenv`keys`meta`prd`save`sv`views`xprev`cols`each`group`last`min`prds`scan`svar`vs`xrank`ww;
    t:{@[{type parse string x};x;`$"Not a function"]} each f!f; 
    x: ([] f:key t; h:{$[-5h=type x;x;0]}each value t);
    x: update p: (parse string@) each f from x where h<>0;
    revDict: (x`p)!(x`f);
    glyphs: asc "~`!@#$%^&*()-=+\\\":'/?.>,<";
    isOnlyGlyphs: {all {any x in glyphs} each x};
    sstring: {$[type[x]=10h;x;string x]};
    func2string:{t: revDict x; $[null[t]|(isOnlyGlyphs sstring x);sstring x;string t]};
    var2string: {[var2string;x] t: type[x]; if[t>=100h; :"Func[",func2string[x],"]";]; 
        if[t=99h; :"Dict(",var2string[key x],": ",var2string[value x],")";];
        at: abs t; $[t=0; "L","[",(", " sv var2string each x),"]"; t>0;"L",string[.Q.t t],"[",(", " sv sstring each x),"]";string[.Q.t neg t],"[",sstring[x],"]"]};
    :var2string[var2string] parse expr
    }""" 
    try:
        return q(query, low_level = True, expr = expr)
    except qtype.QException as e:
        if e.args[0] == b'/':
            raise Exception("""Slash (/) exception; Possible syntax error involving operator slash (/); Correct syntax:
 - ```(f/)x``` or ```f/[x]``` for unary function f, parameter x: converge: apply f repeatedly to x then its result until convergence
 - ```n f/x``` or ```f/[n;x]``` for unary function f, parameter x, integer n: do: apply f to x (and its subsequent result) n times
 - ```t f/x``` or ```t/[n;x]``` f/x for unary function f, parameter x, unary function or data structure t: while: apply f to x (and its subsequent result) until t[result]=0
 - ```(f/)x``` or ```f/[x]``` for binary function f, list x: over: reduce a list x using function f
 - ```x0 f/x``` or ```f/[x0;x]``` for binary function f, list x: over: reduce a list x using function f with initial value x0
 - ```f/[x0;x;y]```, or ```f/[x0;x;y;z]``` etc. for function f with rank > 2, initial value x0, lists x, y, etc.: over: as above (over with starting value) except that the function can consume inputs from multiple lists""")
        else:
            raise e
