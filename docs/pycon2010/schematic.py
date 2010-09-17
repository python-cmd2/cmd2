from turtle import *
hideturtle()
width(6)
pensize = 10
pu()
goto(0,-400)

def rectangle(x, y, _label):
    pu()
    seth(0)
    backward(x / 2)
    fontsize = 40
    pd()
    for i in range(2):
        forward(x)
        left(90)
        forward(y)
        left(90)
    pu()
    forward(x / 2)
    left(90)
    forward(y / 2 - fontsize)
    pd()
    write(_label, align='center', font=('Arial', fontsize, 'bold'))    

rectangle(800, 80, 'cmd')
pu()
forward(80)
rectangle(200, 400, 'cmd2')

while True:
    pass
