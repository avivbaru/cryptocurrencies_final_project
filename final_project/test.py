def check(f):
    def inner(self, addr, *args):
        if addr in self.t:
            return f(self, addr, *args)
        # print("sdf")

    return inner

class a:
    def __init__(self):
        self.t = ['a']
    @check
    def test(self, addr: str, r):
        print(addr)
        print(r)
        print("Dfg")

aa = a()
aa.test("a", "Asdf")
aa.test("Asd", "Adsf")

