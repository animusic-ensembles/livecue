def chain(*iterators):
    for iterator in iterators:
        for element in iterator:
            yield element
