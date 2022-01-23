COLOR = {
    "RED": "\033[91m",
    "GREEN": "\033[92m",
    "YELLOW": "\033[93m",
    "BLUE": "\033[94m",
    "PINK": "\033[95m",
    "END": "\033[0m",
}

def color_text(msg, color):
    return f"{COLOR[color]}{msg}{COLOR['END']}"

def red(msg):
    return color_text(msg, "RED")

def yellow(msg):
    return color_text(msg, "YELLOW")

def green(msg):
    return color_text(msg, "GREEN")

def blue(msg):
    return color_text(msg, "BLUE")

def pink(msg):
    return color_text(msg, "PINK")

# Alias functions
error = red
warn = yellow
success = green
info = blue
header = pink

def confirm(msg):
    ret = input(warn(msg) +  " (y/n)\n> ")
    return ret != "" and ret in "yY"

