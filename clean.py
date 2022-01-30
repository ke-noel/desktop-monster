import os
import random
import time

from dotenv import load_dotenv
import pyautogui
import tkinter as tk
from twilio.rest import Client

# Configurations
X_MAX = 1436                # maximum x position
Y_MAX = 900                 # maximum y position
X_VEL = 8                   # default x velocity
Y_VEL = 5                   # default y velocity
X_IMG_SIZE = 100            # image width
Y_IMG_SIZE = 100            # image height
POKE_LIMIT = 3              # number of pokes before the monster gets angry
ANGRY_ITERS = 100           # time monster is angry for before calming down
STEAL_ITERS = 30            # time until monster gives the mouse back
IDLE_ALERT_ITERS = 10     # time idle before the monster sends users a message
CHASE_SPEED_MULTIPLIER = 4
PETS_ITERS = 30

events = [
    {'name': 'excited', 'weight': 10,   'wait': 100,    'repeat': 5,    'dx': 0,    'dy': 0},
    {'name': 'left',    'weight': 10,   'wait': 70,     'repeat': 10,   'dx': -1,   'dy': 0},
    {'name': 'upleft',  'weight': 15,   'wait': 70,     'repeat': 10,   'dx': -1,   'dy': -1},
    {'name': 'downleft','weight': 15,   'wait': 70,     'repeat': 10,   'dx': -1,   'dy': 1},
    {'name': 'right',   'weight': 10,   'wait': 70,     'repeat': 10,   'dx': 1,    'dy': 0},
    {'name': 'upright', 'weight': 15,   'wait': 70,     'repeat': 10,   'dx': 1,    'dy': -1},
    {'name': 'downright','weight': 15,  'wait': 70,     'repeat': 10,   'dx': 1,    'dy': 1},
    {'name': 'up',      'weight': 5,    'wait': 70,     'repeat': 10,   'dx': 0,    'dy': -1},
    {'name': 'down',    'weight': 5,    'wait': 70,     'repeat': 10,   'dx': 0,    'dy': 1},
    {'name': 'sleep',   'weight': 10,   'wait': 400,    'repeat': 10,    'dx': 0,    'dy': 0},
    {'name': 'munch',   'weight': 0,    'wait': 200,    'repeat': 5,    'dx': 0,    'dy': 0},
    {'name': 'poke',    'weight': 0,    'wait': 100,    'repeat': 2,    'dx': 0,    'dy': 0},
    {'name': 'angry',   'weight': 0,    'wait': 100,    'repeat': 20, 'dx': 0,    'dy': 0},
    {'name': 'steal',   'weight': 0,    'wait': 200,    'repeat': 2, 'dx': 0,    'dy': 0},
    {'name': 'call',    'weight': 0,    'wait': 200,    'repeat': 20,    'dx': 0,    'dy': 0},
    {'name': 'pets',    'weight': 0,    'wait': 200,    'repeat': 500,    'dx': 0,    'dy': 0},
]

# Helper functions
def send_sms(client):
    message = client.messages.create(
        body='Hi there! Your desktop is still open. Hurry back or I might escape!',
        to='+14383348877',
        from_='+17853845636',
        media_url=['https://media.giphy.com/media/l6ugdYOC44rDyEieB5/giphy.gif'],
    )
    #print(message.sid)

def get_random_event_id():
    return random.choices(
        range(len(events)), 
        weights=[e['weight'] for e in events], 
        k=1,
    )[0]

def get_event_id_by_name(event_name):
    for i,e in enumerate(events):
        if e['name'] == event_name:
            return i

class Monster():
    def __init__(self, x, y, window, label, client, logging=True):
        self.x = x
        self.y = y
        self.window = window
        self.label = label
        self.logging = logging

        # Frame selection flags
        self.event_id = -1
        self.frame_id = -1
        self.repeat_count = 0

        # Mood flags
        self.mode = 'random'  # also 'angry'
        self.is_being_petted = False
        self.is_stealing_mouse = False
        self.poke_count = 0
        self.has_mouse_iters = 0
        self.angry_iters = 0
        self.pets_iters = 0

        # Twilio flags
        self.client = client
        self.idle_user_iters = 0
        self.prev_mouse_pos = pyautogui.position()
        self.alert_sent = False

    def _log_event(self):
        print(events[self.event_id]['name'])

    def get_next_frame(self):
        frame = events[self.event_id]['frames'][self.frame_id]
        self.repeat_count = self.repeat_count + 1 if self.frame_id == 1 else self.repeat_count
        if self.frame_id == -1:
            return frame
        self.frame_id = 1 - self.frame_id  # toggle frame
        if self.repeat_count >= events[self.event_id]['repeat']:
            self.frame_id = -1
        return frame

    def _is_under_mouse(self):
        x_mouse, y_mouse = pyautogui.position()
        if x_mouse >= self.x and x_mouse <= self.x + X_IMG_SIZE:
            if y_mouse >= self.y and y_mouse <= self.y + Y_IMG_SIZE:
                return True
        return False

    def random_behaviour(self):
        if self.mode != 'random':
            return

        self._check_idle()

        if self._is_under_mouse() and self.is_stealing_mouse and self.event_id == get_event_id_by_name('sleep'):
            self.is_stealing_mouse = False
        elif self._is_under_mouse() and not self.is_stealing_mouse and self.event_id != get_event_id_by_name('poke'):
            self.being_petted()
            return
        elif not self._is_under_mouse() and self.is_being_petted and self.pets_iters < PETS_ITERS:
            self.mode = 'angry'
            self.is_being_petted = False
            self.pets_iters = 0
            self.angry_iters = 0
            self._set_event_id('angry')
            time.sleep(0.25)
            self.chase_mouse()
            return
        elif self.pets_iters > 0:
            self.pets_iters = 0
            self.is_being_petted = False

        self.is_being_petted = False
        
        # Select a random action or continue the current action
        if self.frame_id == -1:
            # Select new event if needed (signaled by frame_id=-1)
            self.event_id = get_random_event_id()
            self._set_event_id(events[self.event_id]['name'])

        # Handle movement
        dx = events[self.event_id]['dx']
        dy = events[self.event_id]['dy']

        if dx == -1 and self.x - X_VEL >= 0:
            self.x -= random.randint(0, X_VEL)
        elif dx == 1 and self.x + X_VEL <= X_MAX:
            self.x += random.randint(0, X_VEL)
        elif dx != 0:
            # Stop trying to run into a wall
            self.frame_id = -1
        
        if dy == -1 and self.y - Y_VEL >= 0:
            self.y -= random.randint(0, Y_VEL)
        elif dy == 1 and self.y + Y_VEL <= Y_MAX:
            self.y += random.randint(0, Y_VEL)
        elif dy != 0:
            # Stop trying to run into a wall
            self.frame_id = -1

        self.display_new_frame(self.random_behaviour)

    def display_new_frame(self, callback):
        frame = self.get_next_frame()
        self.window.geometry(f'100x100+{str(self.x)}+{str(self.y)}')
        self.label.configure(image=frame)

        if self.is_stealing_mouse:
            # Left-click on mouse to regain control
            self.label.bind('<Button-2>', lambda _: self._let_go_of_mouse())
            pyautogui.moveTo(self.x+50, self.y+50)
            self.has_mouse_iters += 1
            if self.has_mouse_iters >= STEAL_ITERS:
                self.is_stealing_mouse = False
                self.has_mouse_iters = 0

        self.window.after(events[self.event_id]['wait'], callback)

    def chase_mouse(self):
        if self.mode != 'angry':
            return

        if self._is_under_mouse():
            # The monster caught the mouse!
            self._set_event_id('steal')
            self.mode = 'random'
            self.is_stealing_mouse = True
            self.has_mouse_iters = 0
            time.sleep(0.25)
            self.display_new_frame(self.random_behaviour)
            return

        # Follow the mouse!
        x_mouse, y_mouse = pyautogui.position()
        move_x = 0
        move_y = 0
        dx = self.x + 50 - x_mouse
        if dx < 0:
            move_x = 1
        elif dx > 0:
            move_x = -1
        dy = self.y + 50 - y_mouse
        if dy < 0:
            move_y = 1
        elif dy > 0:
            move_y = -1

        self.x += move_x * X_VEL * CHASE_SPEED_MULTIPLIER
        self.y += move_y * Y_VEL * CHASE_SPEED_MULTIPLIER

        self.angry_iters += 1
        if self.angry_iters < ANGRY_ITERS:
            self.display_new_frame(self.chase_mouse)
        else:
            self.mode = 'random'
            self.display_new_frame(self.random_behaviour)

    def poke(self):
        if self.event_id != get_event_id_by_name('sleep'):
            # can only poke sleeping monster
            return
        self._set_event_id('poke')
        self.poke_count += 1

        if self.poke_count > POKE_LIMIT:
            self._set_event_id('angry')
            self.mode = 'angry'
            self.poke_count = 0
            self.is_being_poked = False
            time.sleep(0.25)
            self.display_new_frame(self.chase_mouse)
            return

        self.mode = 'random'
        self.display_new_frame(self.random_behaviour)

    def being_petted(self):
        if self.event_id == get_event_id_by_name('sleep'):
            self.display_new_frame(self.random_behaviour)
            return
        elif not self.is_being_petted:
            self._set_event_id('pets')
            self.is_being_petted = True
        
        self.pets_iters += 1
        
        if self.pets_iters > PETS_ITERS:
            self._set_event_id('sleep')

        self.display_new_frame(self.random_behaviour)

    def _check_idle(self):
        print('checking')
        if pyautogui.position() == self.prev_mouse_pos and not self.alert_sent:
            self.idle_user_iters += 1
            if self.idle_user_iters > IDLE_ALERT_ITERS:
                self.alert_sent = True
                self._set_event_id('call')
                self.display_new_frame(send_sms(self.client))
        else:
            self.idle_user_iters = 0
            self.prev_mouse_pos = pyautogui.position()

    def _let_go_of_mouse(self):
        self.is_stealing_mouse = False
        self.mode = 'random'
        time.sleep(0.5)

    def _set_event_id(self, name):
        self.event_id = get_event_id_by_name(name)
        self.frame_id = 0
        self.repeat_count = 0
        if self.logging:
            self._log_event()



def main():
    # Twilio setup
    load_dotenv()
    twilio_account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    twilio_auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    client = Client(twilio_account_sid, twilio_auth_token)

    window = tk.Tk()

    # Load GIFs
    img_path = 'C:\\Users\\kirae\\Downloads\\imgs\\'
    events[0]['frames'] = [tk.PhotoImage(file=img_path+'excited.gif',format='gif -index %i' %(i)) for i in range(2)]
    events[1]['frames'] = [tk.PhotoImage(file=img_path+'left.gif',format='gif -index %i' %(i)) for i in range(2)]
    events[2]['frames'] = [tk.PhotoImage(file=img_path+'left.gif',format='gif -index %i' %(i)) for i in range(2)]
    events[3]['frames'] = [tk.PhotoImage(file=img_path+'left.gif',format='gif -index %i' %(i)) for i in range(2)]
    events[4]['frames'] = [tk.PhotoImage(file=img_path+'right.gif',format='gif -index %i' %(i)) for i in range(2)]
    events[5]['frames'] = [tk.PhotoImage(file=img_path+'right.gif',format='gif -index %i' %(i)) for i in range(2)]
    events[6]['frames'] = [tk.PhotoImage(file=img_path+'right.gif',format='gif -index %i' %(i)) for i in range(2)]
    events[7]['frames'] = [tk.PhotoImage(file=img_path+'idle.gif',format='gif -index %i' %(i)) for i in range(2)]
    events[8]['frames'] = [tk.PhotoImage(file=img_path+'idle.gif',format='gif -index %i' %(i)) for i in range(2)]
    events[9]['frames'] = [tk.PhotoImage(file=img_path+'sleep.gif',format='gif -index %i' %(i)) for i in range(2)]
    events[10]['frames'] = [tk.PhotoImage(file=img_path+'monster.gif',format='gif -index %i' %(i)) for i in range(2)]
    events[11]['frames'] = [tk.PhotoImage(file=img_path+'angry.gif',format='gif -index %i' %(i)) for i in range(2)]
    events[12]['frames'] = [tk.PhotoImage(file=img_path+'monster.gif',format='gif -index %i' %(i)) for i in range(2)]
    events[13]['frames'] = [tk.PhotoImage(file=img_path+'excited.gif',format='gif -index %i' %(i)) for i in range(2)]
    events[14]['frames'] = [tk.PhotoImage(file=img_path+'phone.gif',format='gif -index %i' %(i)) for i in range(2)]
    events[15]['frames'] = [tk.PhotoImage(file=img_path+'pets.gif',format='gif -index %i' %(i)) for i in range(2)]


    window.config(highlightbackground='black')
    label = tk.Label(window, bd=0, bg='black')
    label.bind('<Button-3>', lambda _: window.destroy())
    window.overrideredirect(True)
    window.wm_attributes('-transparentcolor', 'black')
    label.pack()

    X_MAX = window.winfo_screenwidth() - int(X_IMG_SIZE / 2)
    Y_MAX = window.winfo_screenheight() - int(X_IMG_SIZE / 2) - 75

    x = X_MAX - 300
    y = Y_MAX

    monster = Monster(x, y, window, label, client, logging=False)
    label.bind('<Button-1>', lambda _: monster.poke())
    window.after(100, monster.random_behaviour)
    window.mainloop()


if __name__ == '__main__':
    main()
