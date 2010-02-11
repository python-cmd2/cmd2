import doctest

class TextLineList(list):
    '''A list that "wants" to consist of separate lines of text.
    Splits multi-line strings and flattens nested lists to 
    achieve that.
    Also omits blank lines, strips leading/trailing whitespace.
    
    >>> tll = TextLineList(['my', 'dog\\nhas', '', [' fleas', 'and\\nticks']])
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