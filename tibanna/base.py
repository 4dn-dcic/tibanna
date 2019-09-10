import copy


class SerializableObject(object):
    def __init__(self):
        pass

    def update(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def as_dict(self):
        # use deepcopy so that changing this dictionary later won't affect the SerializableObject
        d = copy.deepcopy(self.__dict__)
        for k in list(d.keys()):
            if d[k] is None:
                del d[k]
        # recursive serialization
        for k, v in d.items():
            if isinstance(v, SerializableObject):
                d[k] = v.as_dict()
            if isinstance(v, list):
                for i, e in enumerate(v):
                    if isinstance(e, SerializableObject):
                        d[k][i] = e.as_dict()
            if isinstance(v, dict):
                for l, w in v.items():
                    if isinstance(w, SerializableObject):
                        d[k][l] = w.as_dict()
        return d
