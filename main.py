import random
import tkinter as tk
import pyautogui
from twilio.rest import Client
from dotenv import load_dotenv
import os

load_dotenv()
twilio_account_sid = os.getenv('TWILIO_ACCOUNT_SID')
twilio_auth_token = os.getenv('TWILIO_AUTH_TOKEN')

client = Client(twilio_account_sid, twilio_auth_token)

X_MAX = 1436
Y_MAX = 900
X_MOVE = 10
Y_MOVE = 10
X_IMG = 100
Y_IMG = 100
POKE_LIMIT = 3
ANGRY_ITERS = 100
STEAL_ITERS = 30
IDLE_ALERT_ITERS = 100

events = [
    {'name': 'excited', 'num_frames': 2, 'weight': 10, 'wait': 100, 'repeat': 5, 'dx': 0, 'dy': 0},
    {'name': 'left', 'num_frames': 2, 'weight': 10, 'wait': 30, 'repeat': 30, 'dx': -1, 'dy': 0},
    {'name': 'right', 'num_frames': 2, 'weight': 10, 'wait': 30, 'repeat': 30, 'dx': 1, 'dy': 0},
    {'name': 'up', 'num_frames': 2, 'weight': 10, 'wait': 30, 'repeat': 30, 'dx': 0, 'dy': -1},
    {'name': 'down', 'num_frames': 2, 'weight': 10, 'wait': 30, 'repeat': 30, 'dx': 0, 'dy': 1},
    {'name': 'sleep', 'num_frames': 2, 'weight': 10, 'wait': 200, 'repeat': 5, 'dx': 0, 'dy': 0},
    {'name': 'munch', 'num_frames': 2, 'weight': 0, 'wait': 200, 'repeat': 5, 'dx': 0, 'dy': 0},
    {'name': 'poke', 'num_frames': 2, 'weight': 0, 'wait': 50, 'repeat': 1, 'dx': 0, 'dy': 0},
    {'name': 'angry', 'num_frames': 2, 'weight': 0, 'wait': 50, 'repeat': 1, 'dx': 0, 'dy': 0},
    {'name': 'stealmouse', 'num_frames': 2, 'weight': 0, 'wait': 200, 'repeat': 5, 'dx': 0, 'dy': 0},
    {'name': 'call', 'num_frames': 2, 'weight': 0, 'wait': 200, 'repeat': 5, 'dx': 0, 'dy': 0},
]

angry = False
poke_count = 0
is_poking = False
has_mouse = False
has_mouse_iters = 0
idle_iters = 0
prev_mouse_pos = pyautogui.position()
alert_sent = False

def send_sms():
    message = client.messages.create(
        body='Hi there! Your desktop is still open. Hurry back or I might escape!',
        to='+14383348877',
        from_='+17853845636',
        media_url=['https://tenor.com/bPMHe.gif'],
    )
    print(message.sid)

# Select a random event id with relative weighting
def get_random_event_id():
    return random.choices(
        range(len(events)), 
        weights=[e['weight'] for e in events], 
        k=1,
    )[0]

# Print each new event to console
def log_event(event_id):
    print(events[event_id]['name'])

# Return the next gif frame
def get_next_frame(event_id, gif_frame_id, repeat_count):
    frame = events[event_id]['frames'][gif_frame_id]
    gif_frame_id += 1
    if gif_frame_id >= events[event_id]['num_frames']:
        repeat_count += 1
        gif_frame_id = -1 if repeat_count >= events[event_id]['repeat'] else 0
    return frame, gif_frame_id, repeat_count

def is_mouseover(x, y):
    x_mouse, y_mouse = pyautogui.position()
    if x_mouse >= x and x_mouse <= x + X_IMG:
        if y_mouse >= y and y_mouse <= y + Y_IMG:
            return True

def chase_mouse(event_id, gif_frame_id, x, y, iters_remaining):
    global angry, has_mouse, has_mouse_iters
    if not angry:
        return

    if is_mouseover(x, y):
        event_id = 9  # steal the mouse
        log_event(event_id)
        frame = events[event_id]['frames'][0]
        window.geometry(f'100x100+{str(x)}+{str(y)}')
        label.configure(image=frame)
        angry = False
        has_mouse = True
        has_mouse_iters = STEAL_ITERS
        update(0, -1, x, y, 0)

    x_mouse, y_mouse = pyautogui.position()
    move_x = 0
    move_y = 0
    dx = x + 50 - x_mouse
    if dx < 0:
        move_x = 1
    elif dx > 0:
        move_x = -1
    dy = y + 50 - y_mouse
    if dy < 0:
        move_y = 1
    elif dy > 0:
        move_y = -1

    x += move_x * X_MOVE
    y += move_y * Y_MOVE

    window.geometry(f'100x100+{str(x)}+{str(y)}')
    frame = events[event_id]['frames'][gif_frame_id]
    label.configure(image=frame)

    iters_remaining -= 1
    if iters_remaining > 0:
        gif_frame_id = 1 - gif_frame_id
        window.after(50, chase_mouse, event_id, gif_frame_id, x, y, iters_remaining)
    else:
        angry = False
        window.after(50, update, 0, -1, x, y, 0)

def free_mouse():
    global has_mouse 
    has_mouse = False

def update(event_id, gif_frame_id, x, y, repeat_count):
    global angry, has_mouse, poke_count, is_poking, has_mouse_iters, idle_iters, alert_sent, prev_mouse_pos
    if angry:
        # Stop any waiting calls from activating
        return

    if pyautogui.position() == prev_mouse_pos and not alert_sent:
        idle_iters += 1
        if idle_iters > IDLE_ALERT_ITERS:
            alert_sent = True
            print('send sms')
            send_sms()
    elif idle_iters > 0:
        idle_iters = 0
        prev_mouse_pos = pyautogui.position()
    
    if is_mouseover(x, y) and not has_mouse:
        if not is_poking:
            event_id = 7  # poke mode
            log_event(event_id)
            poke_count += 1
            is_poking = True

            # Chase the mouse
            if poke_count > POKE_LIMIT:
                event_id = 8
                angry = True
                poke_count = 0
                is_poking = False
                log_event(event_id)
                window.after(500, chase_mouse, event_id, 0, x, y, ANGRY_ITERS)  

        # Mouse poked desktop pet
        gif_frame_id = 0
        repeat_count = 0
    else:
        is_poking = False

    if gif_frame_id == -1:
        # Select new event if needed (signaled by gif_frame_id=-1)
        event_id = get_random_event_id()
        gif_frame_id = 0
        repeat_count = 0
        log_event(event_id)

    # Fetch next frame
    frame, gif_frame_id, repeat_count = get_next_frame(event_id, gif_frame_id, repeat_count)
    
    # Handle movement
    dx = events[event_id]['dx']
    dy = events[event_id]['dy']

    if dx == -1 and x - X_MOVE >= 0:
        x -= X_MOVE
    elif dx == 1 and x + X_MOVE <= X_MAX:
        x += X_MOVE
    elif dy == -1 and y - Y_MOVE >= 0:
        y -= Y_MOVE
    elif dy == 1 and y + Y_MOVE <= Y_MAX:
        y += Y_MOVE
    elif dx != 0 or dy != 0:
        # Stop trying to run into a wall
        gif_frame_id = -1

    window.geometry(f'100x100+{str(x)}+{str(y)}')
    label.configure(image=frame)
    if has_mouse:
        label.bind('<Button-1>', lambda _: free_mouse())
        pyautogui.moveTo(x+50, y+50)
        has_mouse_iters -= 1
        if has_mouse_iters <= 0:
            has_mouse = False
    window.after(events[event_id]['wait'], update, event_id, gif_frame_id, x, y, repeat_count)


### PROGRAM ###
window = tk.Tk()

# Load GIFs
img_path = 'C:\\Users\\kirae\\Downloads\\imgs\\'
events[0]['frames'] = [tk.PhotoImage(file=img_path+'excited.gif',format='gif -index %i' %(i)) for i in range(2)]
events[1]['frames'] = [tk.PhotoImage(file=img_path+'left.gif',format='gif -index %i' %(i)) for i in range(2)]
events[2]['frames'] = [tk.PhotoImage(file=img_path+'right.gif',format='gif -index %i' %(i)) for i in range(2)]
events[3]['frames'] = [tk.PhotoImage(file=img_path+'idle.gif',format='gif -index %i' %(i)) for i in range(2)]
events[4]['frames'] = [tk.PhotoImage(file=img_path+'idle.gif',format='gif -index %i' %(i)) for i in range(2)]
events[5]['frames'] = [tk.PhotoImage(file=img_path+'sleep.gif',format='gif -index %i' %(i)) for i in range(2)]
events[6]['frames'] = [tk.PhotoImage(file=img_path+'monster.gif',format='gif -index %i' %(i)) for i in range(2)]
events[7]['frames'] = [tk.PhotoImage(file=img_path+'angry.gif',format='gif -index %i' %(i)) for i in range(2)]
events[8]['frames'] = [tk.PhotoImage(file=img_path+'monster.gif',format='gif -index %i' %(i)) for i in range(2)]
events[9]['frames'] = [tk.PhotoImage(file=img_path+'excited.gif',format='gif -index %i' %(i)) for i in range(2)]


window.config(highlightbackground='black')
label = tk.Label(window, bd=0, bg='black')
label.bind('<Button-3>', lambda _: window.destroy())
window.overrideredirect(True)
window.wm_attributes('-transparentcolor', 'black')
label.pack()

#window.after(15000, lambda: window.destroy())

X_MAX = window.winfo_screenwidth() - 100
Y_MAX = window.winfo_screenheight() - 130

x = X_MAX - 300
y = Y_MAX

window.after(200, update, -1, -1, x, y, 0)
window.mainloop()
