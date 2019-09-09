from tibanna.nnested_array import (
    combine_two,
    run_on_nested_arrays2
)

def test_combine_two():
    x = combine_two('a', 'b')
    assert x == 'a/b'
    x = combine_two(['a1', 'a2'], ['b1', 'b2'])
    assert x == ['a1/b1', 'a2/b2']
    x = combine_two([['a1', 'a2'], ['b1', 'b2']], [['c1', 'c2'], ['d1', 'd2']])
    assert x == [['a1/c1', 'a2/c2'], ['b1/d1', 'b2/d2']]
    x = combine_two([[['a1', 'a2'], ['b1', 'b2']], [['c1', 'c2'], ['d1', 'd2']]],
                    [[['e1', 'e2'], ['f1', 'f2']], [['g1', 'g2'], ['h1', 'h2']]])
    assert x == [[['a1/e1', 'a2/e2'], ['b1/f1', 'b2/f2']],
                 [['c1/g1', 'c2/g2'], ['d1/h1', 'd2/h2']]]


def test_run_on_nested_arrays2():
    def sum0(a, b):
        return(a + b)
    x = run_on_nested_arrays2(1, 2, sum0)
    assert x == 3
    x = run_on_nested_arrays2([1, 2], [3, 4], sum0)
    assert x == [4, 6]
    x = run_on_nested_arrays2([[1, 2], [3, 4]], [[5, 6], [7, 8]], sum0)
    assert x == [[6, 8], [10, 12]]
