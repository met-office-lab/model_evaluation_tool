"""Middleware utilities"""


class Echo:
    def __init__(self, fmt):
        self.fmt = fmt

    def __call__(self, store, action):
        print(self.fmt.format(action=action))
        yield action


def echo(store, action):
    print(action)
    yield action
