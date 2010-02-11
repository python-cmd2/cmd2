import doctest
def flatten(texts):
    '''
    >>> flatten([['cow', 'cat'], '', 'fish', ['bird']])
    ['cow', 'cat', 'fish', 'bird']
    '''
    result = []
    if isinstance(texts, basestring):
        result.extend(texts.splitlines())
    else:
        for text in texts:
            result.extend(flatten(text))
    result = [r.strip() for r in result if r.strip()]
    return result
doctest.testmod()
