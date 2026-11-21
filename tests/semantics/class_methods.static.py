class Shape:
    name: str
    sides: int

    def __init__(self, name: str, sides: int):
        self.name = name
        self.sides = sides

    def describe(self) -> str:
        return self.name + ":" + str(self.sides)

    def doubled(self) -> int:
        return self.sides * 2

    @classmethod
    def unnamed(cls, sides: int):
        return Shape("?", sides)

    @staticmethod
    def kind() -> str:
        return "shape"

class Square(Shape):
    def __init__(self, side: int):
        super().__init__("square", 4)
        self.side = side

    def area(self) -> int:
        return self.side * self.side

def main():
    s: Shape = Shape("tri", 3)
    print(s.describe())
    print(s.doubled())
    q: Square = Square(5)
    print(q.describe())
    print(q.area())
    u: Shape = Shape.unnamed(6)
    print(u.describe())
    print(Shape.kind())
    print(q.doubled())
    print(q.name)
