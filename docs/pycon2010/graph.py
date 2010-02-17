from turtle import *
pu()
goto(-400,-400)

def label(txt):
    write(txt, font=('Arial', 20, 'italic'))
hideturtle()
width(6)

def line(len, _label):
    start = pos()
    pd()
    forward(len)
    pu()
    forward(30)
    pd()
    label(_label)
    pu()
    goto(start)

def tech(x, y, _label):
    pu()
    goto(x, y)
    pd()
    write(_label, font=('Arial', 40, 'bold'))
    pu()
    
line(600, "Easy to write")
left(90)
line(600, "Easy to use")

tech(-360, 160, 'GUI')
tech(-390, 100, 'AJAX')
tech(-300, -10, 'webapp')
tech(190, -380, 'CLU')
tech(60, -320, 'TUI')
tech(100, -210, 'cmd')
tech(80, -80, 'cmd2')

while True:
    pass