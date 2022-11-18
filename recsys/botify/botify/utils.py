import pickle


def to_bytes(instance):
    return pickle.dumps(instance)


def from_bytes(bts):
    return pickle.loads(bts)
