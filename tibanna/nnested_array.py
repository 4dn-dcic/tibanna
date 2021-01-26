def combine_two(a, b, delimiter='/'):
    """returns an n-nested array of strings a+delimiter+b
    a and b (e.g. uuids and object_keys) can be a singlet,
    an array, an array of arrays or an array of arrays of arrays ...
    example:
    >>> a = ['a','b',['c','d']]
    >>> b = ['e','f',['g','h']]
    >>> combine_two(a, b)
    ['a/e','b/f',['c/g','d/h']]
    """
    if isinstance(a, list):
        if not isinstance(b, list):
            raise Exception("can't combine list and non-list")
        if len(a) != len(b):
            raise Exception("Can't combine lists of different lengths")
        return [combine_two(a_, b_) for a_, b_, in zip(a, b)]
    else:
        return(str(a) + delimiter + str(b))


def run_on_nested_arrays1(a, func, **param):
    """run func on each pair of element in a and b:
    a and b can be singlets, an array, an array of arrays, an array of arrays of arrays ...
    The return value is a flattened array
    """
    if isinstance(a, list):
        return([run_on_nested_arrays1(_, func, **param) for _ in a])
    else:
        return(func(a, **param))


def run_on_nested_arrays2(a, b, func, **param):
    """run func on each pair of element in a and b:
    a and b can be singlets, an array, an array of arrays, an array of arrays of arrays ...
    The return value is a flattened array
    """
    if isinstance(a, list):
        if not isinstance(b, list):
            raise Exception("can't combine list and non-list")
        if len(a) != len(b):
            raise Exception("Can't combine lists of different lengths")
        return([run_on_nested_arrays2(a_, b_, func, **param) for a_, b_ in zip(a, b)])
    else:
        return(func(a, b, **param))


def create_dim(a, dim='', empty=False):
    """create dimension array for n-nested array
    example:
    >>> create_dim([[1,2],[3,4],[5,6,[7,8],]])
    [['0-0', '0-1'], ['1-0', '1-1'], ['2-0', '2-1', ['2-2-0', '2-2-1']]]
    >>> create_dim(5)
    ''
    >>> create_dim([5,5])
    ['0', '1']
    >>> create_dim([5,5], empty=True)
    ['', '']
    """
    if isinstance(a, list):
        if dim:
            prefix = dim + '-'
        else:
            prefix = ''
        if empty:
            return([create_dim(a_, empty=empty) for a_ in a])
        else:
            return([create_dim(a_, prefix + str(i)) for i, a_ in enumerate(a)])
    else:
        return(dim)


def flatten(a):
    """recursively flatten n-nested array
    example:
    >>> flatten([[1,2],[3,4],[5,6,[7,8],]])
    [1, 2, 3, 4, 5, 6, 7, 8]
    """
    if isinstance(a, list):
        b = list()
        for a_ in a:
            if isinstance(a_, list):
                b.extend(flatten(a_))
            else:
                b.append(a_)
        return(b)
    else:
        return(a)
