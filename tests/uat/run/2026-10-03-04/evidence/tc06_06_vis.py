from tc06lib import sc


def vis(env, name):
    def walk(nodes):
        for n in nodes or []:
            if n.get("name") == name:
                return n.get("visibility")
            v = walk(n.get("children"))
            if v is not None:
                return v
        return None
    return walk(sc(env).get("tree"))
