
# this is a custom class with length and width
# now we can initialize it with 10, 20
# so whenevner we have to iterate over it we can get length first 

# Topic: Custom Classes in Python

# Description: You are tasked with creating a Rectangle class with the following requirements:

# An instance of the Rectangle class requires length:int and width:int to be initialized.
# We can iterate over an instance of the Rectangle class 
# When an instance of the Rectangle class is iterated over, we first get its length in the format: {'length': <VALUE_OF_LENGTH>} followed by the width {width: <VALUE_OF_WIDTH>}

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