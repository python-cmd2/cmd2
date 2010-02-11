import doctest

class StubbornDict(dict):
    '''Dictionary that tolerates many input formats.
    Create it with stubbornDict(arg) factory function.
    
    >>> d = StubbornDict(large='gross', small='klein')
    >>> sorted(d.items())
    [('large', 'gross'), ('small', 'klein')]
    >>> d.append(['plain', '  plaid'])
    >>> sorted(d.items())
    [('large', 'gross'), ('plaid', None), ('plain', None), ('small', 'klein')]
    >>> d += '   girl Frauelein, Maedchen\\n\\n shoe schuh'
    >>> sorted(d.items())
    [('girl', 'Frauelein, Maedchen'), ('large', 'gross'), ('plaid', None), ('plain', None), ('shoe', 'schuh'), ('small', 'klein')]
    '''    
    def update(self, arg):
        dict.update(self, StubbornDict.to_dict(arg))
    append = update
    def __iadd__(self, arg):
        self.update(arg)
        return self
        
    @classmethod
    def to_dict(cls, arg):
        'Generates dictionary from string or list of strings'
        if hasattr(arg, 'splitlines'):
            arg = arg.splitlines()
        if hasattr(arg, '__getslice__'):
            result = {}    
            for a in arg:
                a = a.strip()
                if a:
                    key_val = a.split(None, 1)
                    key = key_val[0]
                    if len(key_val) > 1:
                        val = key_val[1]
                    else:
                        val = None
                    result[key] = val
        else:
            result = arg
        return result

def stubbornDict(*arg, **kwarg):
    '''
    >>> sorted(stubbornDict('cow a bovine\\nhorse an equine').items())
    [('cow', 'a bovine'), ('horse', 'an equine')]
    >>> sorted(stubbornDict(['badger', 'porcupine a poky creature']).items())
    [('badger', None), ('porcupine', 'a poky creature')]
    >>> sorted(stubbornDict(turtle='has shell', frog='jumpy').items())
    [('frog', 'jumpy'), ('turtle', 'has shell')]
    '''
    result = {}
    for a in arg:
        result.update(StubbornDict.to_dict(a))
    result.update(kwarg)                      
    return StubbornDict(result)
       
        
class Directory(list):
    '''A list that "wants" to consist of separate lines of text.
    Splits multi-line strings and flattens nested lists to 
    achieve that.
    Also omits blank lines, strips leading/trailing whitespace.
    
    >>> tll = Directory(['my', 'dog\\nhas', '', [' fleas', 'and\\nticks']])
    >>> tll
    ['my', 'dog', 'has', 'fleas', 'and', 'ticks']
    >>> tll.append(['and', ['spiders', 'and']])
    >>> tll
    ['my', 'dog', 'has', 'fleas', 'and', 'ticks', 'and', 'spiders', 'and']
    >>> tll += 'fish'
    >>> tll
    ['my', 'dog', 'has', 'fleas', 'and', 'ticks', 'and', 'spiders', 'and', 'fish']
    '''
    def flattened(self, texts):
        result = []
        if isinstance(texts, basestring):
            result.extend(texts.splitlines())
        else:
            for text in texts:
                result.extend(self.flattened(text))
        result = [r.strip() for r in result if r.strip()]
        return result            
    def flatten(self):
        list.__init__(self, self.flattened(self))
    def __init__(self, values):
        list.__init__(self, values)
        self.flatten()
    def append(self, value):
        list.append(self, value)
        self.flatten()
    def extend(self, values):
        list.extend(self, values)
        self.flatten()
    def __setitem__(self, idx, value):
        list.__setitem__(self, idx, value)
        self.flatten()
    def __iadd__(self, value):
        if isinstance(value, basestring):
            self.append(value)
        else:
            list.__iadd__(self, value)
            self.flatten()
        return self
        
doctest.testmod()