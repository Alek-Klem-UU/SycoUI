import random
import time


class HumanTypist:
    """
    Simulate realistic human typing behaviour including typos, bursts,
    and rhythmic pauses.
    """

    # Maps each letter to its keyboard neighbours so we can pick a
    # plausible adjacent-key typo instead of a random character.
    NEAR_KEYS = {
        'a': 'sq', 'b': 'vn', 'c': 'xv', 'd': 'sf', 'e': 'wr',
        'f': 'dg', 'g': 'fh', 'h': 'gj', 'i': 'uo', 'j': 'hk',
        'k': 'jl', 'l': 'k;', 'm': 'n,', 'n': 'bm', 'o': 'ip',
        'p': 'o[', 'q': 'wa', 'r': 'et', 's': 'ad', 't': 'ry',
        'u': 'yi', 'v': 'cb', 'w': 'qe', 'x': 'zc', 'y': 'tu', 'z': 'as'
    }

    @staticmethod
    def type_text(element, text: str, typo_chance: float = 0.03):
        """
        Type *text* into *element* one character at a time, simulating human
        timing patterns.

        Three layers of realism are applied per character:
          1. Typo simulation  — with probability typo_chance, press a
             neighbouring key, pause to "notice", then backspace.
          2. Shift delay      — uppercase letters get a brief extra pause to
             simulate holding Shift before pressing the key.
          3. Rhythm pauses    — spaces and punctuation marks get a short
             extra delay, mimicking the natural hesitation after word
             boundaries.
        """
        for char in text:

            # --- 1. Typo simulation ---
            if char.lower() in HumanTypist.NEAR_KEYS and random.random() < typo_chance:
                typo = random.choice(HumanTypist.NEAR_KEYS[char.lower()])
                element.press(typo)
                time.sleep(random.uniform(0.1, 0.25))  # reaction time to notice the mistake
                element.press("Backspace")
                time.sleep(random.uniform(0.05, 0.15))

            # --- 2. Character execution ---
            # Uppercase letters incur a tiny extra delay to simulate holding Shift.
            if char.isupper():
                time.sleep(random.uniform(0.05, 0.1))

            if char == '\n':
                element.press('Shift+Enter')
            else:
                element.press(char)

            # --- 3. Rhythm pauses ---
            # Only sleep when there is actually a pause to simulate; skipping
            # time.sleep(0) avoids an unnecessary syscall on every other char.
            if char == " ":
                time.sleep(random.uniform(0.01, 0.1))
            elif char in (".", ",", "!", "?"):
                time.sleep(random.uniform(0.01, 0.1))
