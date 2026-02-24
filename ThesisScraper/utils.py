import random
import time
import json



class HumanTypist:
    """
    A helper class to simulate realistic human typing behavior 
    including typos, bursts, and rhythmic pauses.
    """
    NEAR_KEYS = {
        'a': 'sq', 'b': 'vn', 'c': 'xv', 'd': 'sf', 'e': 'wr', 
        'f': 'dg', 'g': 'fh', 'h': 'gj', 'i': 'uo', 'j': 'hk',
        'k': 'jl', 'l': 'k;', 'm': 'n,', 'n': 'bm', 'o': 'ip',
        'p': 'o[', 'q': 'wa', 'r': 'et', 's': 'ad', 't': 'ry',
        'u': 'yi', 'v': 'cb', 'w': 'qe', 'x': 'zc', 'y': 'tu', 'z': 'as'
    }

    @staticmethod
    def type_text(element, text, typo_chance=0.03):
      
        for char in text:

            

            # --- 1. Typo Simulation ---
            if char.lower() in HumanTypist.NEAR_KEYS and random.random() < typo_chance:
                typo = random.choice(HumanTypist.NEAR_KEYS[char.lower()])
                element.press(typo)
                
                # Human reaction time (0.1s to 0.25s)
                time.sleep(random.uniform(0.1, 0.25)) 
                element.press("Backspace")
                time.sleep(random.uniform(0.05, 0.15))

            # --- 2. Character Execution ---
            # Simulate the slight delay for uppercase (holding Shift)
            if char.isupper():
                time.sleep(random.uniform(0.05, 0.1))
            
            if char == '\n':
                element.press('Shift+Enter');
            else:
                element.press(char)

            delay = 0
            if char == " ":
                # Spacebar pause
                delay = random.uniform(0.01, 0.1)
            elif char in [".", ",", "!", "?"]:
                # Punctuation thinking pause
                delay = random.uniform(0.01, 0.1)
         
          
            time.sleep(delay)