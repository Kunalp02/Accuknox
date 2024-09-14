
# this is a custom class with length and width
# now we can initialize it with 10, 20
# so whenevner we have to iterate over it we can get length first 
class Rectangle:
    def __init__(self, length, width) -> None:
        self.length = length
        self.width = width
        
    def __iter__(self):
        yield{'length': self.length}
        yield{'width': self.width}
    
rectangle = Rectangle(10, 20)

for item in rectangle:
    print(item)