# 继承：子类记录 (parent Base) 共享父类槽位，父类方法/访问器在子类实例上原生可用。
# 守住的核心点：继承字段由**声明者**的访问器读写（子类不能用自己的 -x-set!），
# 且父类方法读 self.<父类字段> 时不能读到 #f（扁平记录 + 拷贝方法的旧实现就栽在这）。
class Animal:
    name: str
    kind: str

    def __init__(self, name: str):
        self.name = name
        self.kind = "animal"

    def label(self) -> str:
        return self.kind + ":" + self.name

    def shout(self):
        print("shout", self.label())


class Dog(Animal):
    legs: int

    def __init__(self, name: str):
        self.name = name
        self.kind = "dog"
        self.legs = 4

    def bark(self):
        print("bark", self.label(), self.legs)


class Puppy(Dog):
    size: int

    def __init__(self, name: str):
        self.name = name
        self.kind = "puppy"
        self.legs = 4
        self.size = 1

    def small(self):
        print("small", self.label(), self.size)


def main():
    a: Animal = Animal("rex")
    a.shout()
    d: Dog = Dog("fido")
    d.shout()
    d.bark()
    print(d.label(), d.legs)
    p: Puppy = Puppy("bit")
    p.small()
    p.shout()
    print(p.label(), p.legs, p.size)
