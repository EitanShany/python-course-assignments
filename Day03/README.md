# Day 03 - Tumor Volume Calculator
 
## הישתמשתי בChetGPT לביצוע המשימה

העתקתי לChet את המשימה וביקשתי שיעבור איתי שלב שלב לפתור אותה
נקודות שלא היו לי ברורות ביקשתי שיסביר:

נתקדם מסודר: קודם נבנה את מבנה התיקייה והקובץ המרכזי של החישוב, ורק אחר כך נוסיף שלוש דרכי הפעלה ובדיקות.

---

מעולה. נתחיל מ־**שלב 1: יצירת תיקיית day03 והעתקת הקובץ מ־day2**.

## שלב 1 — צור תיקייה חדשה

בתוך ה־repository שלך:

```text
python-course-assignments
```

צור תיקייה חדשה בשם:

```text
day03
```

המבנה צריך להיראות בערך כך:

```text
python-course-assignments/
├── day02/
└── day03/
```

## שלב 2 — העתק את הקובץ מהמשימה הקודמת

אם בקובץ של `day02` היה לך למשל קובץ בשם:

```text
tumor_volume_excel.py
```

או שם דומה, תעתיק אותו לתוך:

```text
day03
```

בשלב הזה עדיין לא משנים את הקוד.

## שלב 3 — צור קובץ חדש לספרייה

בתוך `day03`, צור קובץ חדש בשם:

```text
tumor_volume.py
```

זה יהיה הקובץ שבו נשים את הפונקציה המרכזית של החישוב.

שים בו כרגע את הקוד הזה:

```python
def calculate_tumor_volume(length, width):
    """
    Calculate subcutaneous tumor volume in mice.

    Formula:
    Tumor Volume = (width^2 * length) / 2

    Parameters:
    length (float): Tumor length
    width (float): Tumor width

    Returns:
    float: Calculated tumor volume

    Raises:
    ValueError: If width is greater than length
    """

    if width > length:
        raise ValueError("Width cannot be greater than length.")

    return (width ** 2 * length) / 2
```

בסוף שלב זה התיקייה שלך צריכה להיראות כך:

```text
day03/
├── tumor_volume.py
└── הקובץ שהעתקת מ-day2
```

אחרי שסיימת את זה, נמשיך ל־**שלב 4: יצירת הגרסה הראשונה עם input()**.

---

## בדיקה לגבי התנאי `if width > length`

נכון.

בתנאי הזה:

```python
if width > length:
```

הודעת שגיאה תופיע **רק אם הרוחב גדול מהאורך**.

כלומר:

```python
width = 6
length = 6
```

זה **לא ייחשב שגיאה**, כי `6 > 6` הוא False.

וזה הגיוני במקרה שלך, כי לפעמים גידול יכול להיות כמעט עגול, ואז האורך והרוחב יכולים להיות שווים או כמעט שווים.

אם היית כותב:

```python
if width >= length:
```

אז גם מצב של שוויון היה נחשב שגיאה — וזה פחות מתאים למה שסיכמנו.

---

מעולה. עכשיו נעשה את **שלב 4: גרסה ראשונה עם ****************`input()`**.

בתוך תיקיית `day03`, צור קובץ חדש בשם:

```text
input_version.py
```

שים בו את הקוד הבא:

```python
from tumor_volume import calculate_tumor_volume


def main():
    try:
        length = float(input("Enter tumor length: "))
        width = float(input("Enter tumor width: "))

        volume = calculate_tumor_volume(length, width)

        print(f"Tumor volume is: {volume}")

    except ValueError as error:
        print(f"Error: {error}")


if __name__ == "__main__":
    main()
```

## מה הקובץ הזה עושה

הקובץ הזה לא מחשב בעצמו את נפח הגידול.
הוא רק:

1. מבקש מהמשתמש להכניס `length`
2. מבקש מהמשתמש להכניס `width`
3. שולח אותם לפונקציה שבקובץ `tumor_volume.py`
4. מדפיס את התוצאה

## איך מריצים

מתוך התיקייה `day03`, הרץ:

```bash
py input_version.py
```

לדוגמה, אם תכניס:

```text
Enter tumor length: 10
Enter tumor width: 5
```

תקבל:

```text
Tumor volume is: 125.0
```

אם תכניס בטעות:

```text
Enter tumor length: 5
Enter tumor width: 10
```

תקבל:

```text
Error: Width cannot be greater than length.
```

אחרי שזה עובד, נמשיך לגרסה השנייה עם `sys.argv`.

---

עכשיו נעשה את **שלב 5: גרסה שנייה עם command line / ****************`sys.argv`**.

בתוך תיקיית `day03`, צור קובץ חדש בשם:

```text
argv_version.py
```

שים בו את הקוד הבא:

```python
import sys
from tumor_volume import calculate_tumor_volume


def main():
    try:
        if len(sys.argv) != 3:
            print("Usage: py argv_version.py <length> <width>")
            return

        length = float(sys.argv[1])
        width = float(sys.argv[2])

        volume = calculate_tumor_volume(length, width)

        print(f"Tumor volume is: {volume}")

    except ValueError as error:
        print(f"Error: {error}")


if __name__ == "__main__":
    main()
```

## איך מריצים

מתוך התיקייה `day03`:

```bash
py argv_version.py 10 5
```

הפלט יהיה:

```text
Tumor volume is: 125.0
```

כאן:

```bash
py argv_version.py 10 5
```

המשמעות היא:

```text
10 = length
5 = width
```

## בדיקת שגיאה

אם תריץ:

```bash
py argv_version.py 5 10
```

תקבל:

```text
Error: Width cannot be greater than length.
```

## בדיקה אם חסר קלט

אם תריץ רק:

```bash
py argv_version.py
```

תקבל:

```text
Usage: py argv_version.py <length> <width>
```

אחרי שזה עובד, נמשיך ל־**שלב 6: גרסת GUI עם tkinter**.

---

## הסבר לקוד `argv_version.py`

זה הקוד:

```python
import sys
from tumor_volume import calculate_tumor_volume


def main():
    try:
        if len(sys.argv) != 3:
            print("Usage: py argv_version.py <length> <width>")
            return

        length = float(sys.argv[1])
        width = float(sys.argv[2])

        volume = calculate_tumor_volume(length, width)

        print(f"Tumor volume is: {volume}")

    except ValueError as error:
        print(f"Error: {error}")


if __name__ == "__main__":
    main()
```

### 1. ייבוא ספריות

```python
import sys
```

`sys` היא ספרייה מובנית בפייתון.
אנחנו משתמשים בה כדי לקרוא נתונים שהמשתמש מכניס כבר בזמן הרצת הקובץ מה־terminal.

לדוגמה:

```bash
py argv_version.py 10 5
```

במקרה הזה `10` ו־`5` הם ערכים שהועברו לתוכנית דרך שורת הפקודה.

```python
from tumor_volume import calculate_tumor_volume
```

כאן אנחנו מייבאים את הפונקציה שכתבנו בקובץ הנפרד:

```text
tumor_volume.py
```

כלומר הקובץ `argv_version.py` לא מחשב בעצמו את נפח הגידול.
הוא משתמש בפונקציה המרכזית שכבר קיימת.

זה בדיוק מה שהמשימה ביקשה:
שכל גרסאות התוכנית ישתמשו ב־shared library.

### 2. הפונקציה `main`

```python
def main():
```

זו הפונקציה הראשית של התוכנית.

בתוכה שמים את הפעולות שהתוכנית צריכה לבצע:

1. לבדוק שהמשתמש הכניס שני ערכים.
2. להמיר אותם למספרים.
3. לחשב נפח גידול.
4. להדפיס תוצאה.

### 3. בלוק `try`

```python
try:
```

המשמעות היא:
“נסה להריץ את הקוד הבא, ואם יש שגיאה מסוג מסוים — נטפל בה בצורה מסודרת.”

אנחנו צריכים את זה כי יכולות להיות שגיאות, למשל:

* המשתמש הכניס טקסט במקום מספר.
* המשתמש הכניס רוחב גדול מהאורך.

### 4. בדיקה כמה ערכים המשתמש הכניס

```python
if len(sys.argv) != 3:
```

`sys.argv` היא רשימה של הערכים שהגיעו משורת הפקודה.

אם מריצים:

```bash
py argv_version.py 10 5
```

אז הרשימה היא בערך:

```python
["argv_version.py", "10", "5"]
```

כלומר יש בה **3 פריטים**:

```text
0: שם הקובץ
1: length
2: width
```

לכן אנחנו בודקים:

```python
if len(sys.argv) != 3:
```

כלומר:
אם אין בדיוק 3 פריטים — שם הקובץ + שני מספרים — אז הקלט לא תקין.

### 5. הודעת שימוש

```python
print("Usage: py argv_version.py <length> <width>")
return
```

אם המשתמש לא הכניס נכון את הערכים, התוכנית תדפיס הסבר איך להריץ אותה:

```bash
py argv_version.py <length> <width>
```

לדוגמה:

```bash
py argv_version.py 10 5
```

הפקודה:

```python
return
```

עוצרת את הפונקציה `main`, ולכן התוכנית לא ממשיכה לחישוב.

### 6. קריאת הערכים

```python
length = float(sys.argv[1])
width = float(sys.argv[2])
```

כאן אנחנו לוקחים את שני הערכים מה־terminal.

חשוב: הערכים ב־`sys.argv` מגיעים תמיד כטקסט, אפילו אם כתבת מספר.

כלומר `"10"` הוא טקסט, לא מספר.

לכן אנחנו ממירים אותם ל־`float`:

```python
float("10")
```

הופך ל:

```python
10.0
```

בחרנו `float` ולא `int` כי במדידות אמיתיות של גידולים יכולים להיות ערכים עשרוניים, למשל:

```text
10.5
```

### 7. חישוב נפח הגידול

```python
volume = calculate_tumor_volume(length, width)
```

כאן מתבצע החישוב בפועל, אבל לא בתוך הקובץ הזה.

הקובץ קורא לפונקציה שנמצאת ב־`tumor_volume.py`.

לדוגמה, אם:

```python
length = 10
width = 5
```

אז הפונקציה מחזירה:

```python
125.0
```

לפי הנוסחה:

```text
(width² × length) / 2
```

### 8. הדפסת התוצאה

```python
print(f"Tumor volume is: {volume}")
```

זו הדפסה רגילה של התוצאה.

האות `f` לפני הטקסט מאפשרת להכניס משתנים לתוך המשפט.

למשל אם:

```python
volume = 125.0
```

אז יודפס:

```text
Tumor volume is: 125.0
```

### 9. טיפול בשגיאות

```python
except ValueError as error:
    print(f"Error: {error}")
```

אם במהלך הקוד הייתה שגיאה מסוג `ValueError`, התוכנית לא תקרוס, אלא תדפיס הודעת שגיאה מסודרת.

שתי דוגמאות:

אם המשתמש כתב:

```bash
py argv_version.py abc 5
```

אז `float("abc")` יגרום לשגיאה.

אם המשתמש כתב:

```bash
py argv_version.py 5 10
```

אז הפונקציה שלנו תייצר שגיאה כי:

```python
width > length
```

בשני המקרים התוכנית תציג הודעת שגיאה במקום להתרסק.

### 10. החלק האחרון

```python
if __name__ == "__main__":
    main()
```

המשמעות:
אם מריצים את הקובץ הזה ישירות — תפעיל את `main()`.

כלומר כשמריצים:

```bash
py argv_version.py 10 5
```

אז התוכנית מתחילה לעבוד.

אבל אם בעתיד קובץ אחר ייבא את `argv_version.py`, הפונקציה `main()` לא תרוץ אוטומטית.

זו צורת כתיבה מקובלת ונכונה בפייתון.

---

## מה המשמעות של `!=`

`!=` בפייתון פירושו:

```python
not equal
```

כלומר: **לא שווה**.

לדוגמה:

```python
5 != 3
```

זה נכון (`True`), כי 5 לא שווה ל־3.

אבל:

```python
5 != 5
```

זה לא נכון (`False`), כי 5 כן שווה ל־5.

בקוד שלנו:

```python
if len(sys.argv) != 3:
```

המשמעות היא:

```text
אם מספר הפריטים ב־sys.argv לא שווה ל־3
```

אז תדפיס הודעת שימוש ותעצור.

כלומר, אנחנו רוצים שהתוכנית תקבל בדיוק:

```bash
py argv_version.py 10 5
```

שזה נותן 3 פריטים:

```python
["argv_version.py", "10", "5"]
```

אם המשתמש הכניס פחות או יותר מזה — זו בעיה, ולכן התנאי מתקיים.

---

## האם `len` זה אורך?

כן. `len` זה קיצור של **length**, כלומר **אורך**.

אבל בפייתון `len()` לא מודד אורך פיזי, אלא **כמה פריטים יש בתוך משהו**.

לדוגמה:

```python
len("Hello")
```

יחזיר:

```text
5
```

כי במילה `"Hello"` יש 5 תווים.

דוגמה עם רשימה:

```python
len([10, 20, 30])
```

יחזיר:

```text
3
```

כי ברשימה יש 3 פריטים.

במקרה שלנו:

```python
len(sys.argv)
```

בודק כמה פריטים המשתמש הכניס בשורת הפקודה.

לדוגמה:

```bash
py argv_version.py 10 5
```

נותן:

```python
["argv_version.py", "10", "5"]
```

ולכן:

```python
len(sys.argv)
```

יחזיר:

```text
3
```

---

## מה זה ה־`f` ב־`print(f"Tumor volume is: {volume}")`

ה־`f` אומר שזה **f-string** — דרך נוחה לשלב משתנים בתוך טקסט.

לדוגמה:

```python
volume = 125
print(f"Tumor volume is: {volume}")
```

ידפיס:

```text
Tumor volume is: 125
```

כל מה שנמצא בתוך סוגריים מסולסלים `{}` מוחלף בערך של המשתנה.

בלי `f`, זה לא יעבוד כמו שאתה רוצה:

```python
print("Tumor volume is: {volume}")
```

ידפיס ממש את הטקסט:

```text
Tumor volume is: {volume}
```

אפשר לחשוב על זה כך:

```python
f"Tumor volume is: {volume}"
```

פירושו:
“צור משפט, ובמקום `{volume}` שים את הערך האמיתי של המשתנה `volume`.”

---

## הסבר על `except ValueError as error`

השורות האלה הן טיפול בשגיאה:

```python
except ValueError as error:
    print(f"Error: {error}")
```

המשמעות:

```python
except ValueError
```

אם בתוך ה־`try` קרתה שגיאה מסוג `ValueError`, אל תקריס את התוכנית — תיכנס לכאן.

`ValueError` יכול לקרות למשל בשני מקרים אצלנו:

```python
length = float(sys.argv[1])
```

אם המשתמש כתב טקסט במקום מספר:

```bash
py argv_version.py abc 5
```

אז `float("abc")` יוצר `ValueError`.

וגם כאן:

```python
raise ValueError("Width cannot be greater than length.")
```

אם הפונקציה שלנו זיהתה ש־`width > length`.

```python
as error
```

זה אומר: שמור את פרטי השגיאה בתוך משתנה בשם `error`.

לדוגמה, אם השגיאה הייתה:

```text
Width cannot be greater than length.
```

אז המשתנה `error` מכיל את ההודעה הזו.

```python
print(f"Error: {error}")
```

מדפיס הודעת שגיאה מסודרת למשתמש.

לדוגמה:

```text
Error: Width cannot be greater than length.
```

או אם המשתמש הכניס טקסט במקום מספר:

```text
Error: could not convert string to float: 'abc'
```

כלומר, במקום שהתוכנית תקרוס עם הודעת שגיאה ארוכה ומבלבלת, היא מציגה הודעה קצרה וברורה.

---

מעולה. עכשיו נעשה את **שלב 6: גרסת GUI עם ****************`tkinter`**.

בתוך תיקיית `day03`, צור קובץ חדש בשם:

```text
gui_version.py
```

שים בו את הקוד הבא:

```python
import tkinter as tk
from tumor_volume import calculate_tumor_volume


def calculate():
    try:
        length = float(length_entry.get())
        width = float(width_entry.get())

        volume = calculate_tumor_volume(length, width)

        result_label.config(text=f"Tumor volume is: {volume}")

    except ValueError as error:
        result_label.config(text=f"Error: {error}")


window = tk.Tk()
window.title("Tumor Volume Calculator")

length_label = tk.Label(window, text="Tumor length:")
length_label.pack()

length_entry = tk.Entry(window)
length_entry.pack()

width_label = tk.Label(window, text="Tumor width:")
width_label.pack()

width_entry = tk.Entry(window)
width_entry.pack()

calculate_button = tk.Button(window, text="Calculate", command=calculate)
calculate_button.pack()

result_label = tk.Label(window, text="")
result_label.pack()

window.mainloop()
```

## איך מריצים

מתוך התיקייה `day03`:

```bash
py gui_version.py
```

אמור להיפתח חלון קטן שבו יש:

```text
Tumor length
Tumor width
Calculate button
Result
```

## מה חשוב כאן

גם כאן החישוב עצמו **לא נמצא בקובץ ה־GUI**.

הקובץ משתמש בפונקציה המרכזית:

```python
from tumor_volume import calculate_tumor_volume
```

כלומר שלושת הקבצים:

```text
input_version.py
argv_version.py
gui_version.py
```

כולם משתמשים באותו קובץ:

```text
tumor_volume.py
```

וזה בדיוק מה שהמשימה ביקשה:
**Create 3 versions of the program… Each one uses the shared library.**

אחרי שזה עובד, נמשיך ל־**שלב 7: קובץ בדיקות**.

---

## שיפור ה־GUI: הגדלת החלון, כפתור Exit וצבעים

כן. אפשר לשפר את ה־GUI בלי לשנות את החישוב עצמו.

תחליף את כל הקוד בקובץ:

```text
gui_version.py
```

בקוד הזה:

```python
import tkinter as tk
from tumor_volume import calculate_tumor_volume


def calculate():
    try:
        length = float(length_entry.get())
        width = float(width_entry.get())

        volume = calculate_tumor_volume(length, width)

        result_label.config(
            text=f"Tumor volume is: {volume}",
            fg="darkgreen"
        )

    except ValueError as error:
        result_label.config(
            text=f"Error: {error}",
            fg="red"
        )


def exit_program():
    window.destroy()


window = tk.Tk()
window.title("Tumor Volume Calculator")
window.geometry("420x320")
window.configure(bg="#f2f2f2")

title_label = tk.Label(
    window,
    text="Tumor Volume Calculator",
    font=("Arial", 16, "bold"),
    bg="#f2f2f2",
    fg="#333333"
)
title_label.pack(pady=15)

length_label = tk.Label(
    window,
    text="Tumor length:",
    font=("Arial", 11),
    bg="#f2f2f2"
)
length_label.pack()

length_entry = tk.Entry(
    window,
    font=("Arial", 11),
    width=20
)
length_entry.pack(pady=5)

width_label = tk.Label(
    window,
    text="Tumor width:",
    font=("Arial", 11),
    bg="#f2f2f2"
)
width_label.pack()

width_entry = tk.Entry(
    window,
    font=("Arial", 11),
    width=20
)
width_entry.pack(pady=5)

calculate_button = tk.Button(
    window,
    text="Calculate",
    font=("Arial", 11, "bold"),
    bg="#4CAF50",
    fg="white",
    width=15,
    command=calculate
)
calculate_button.pack(pady=10)

exit_button = tk.Button(
    window,
    text="Exit",
    font=("Arial", 11),
    bg="#cc4444",
    fg="white",
    width=15,
    command=exit_program
)
exit_button.pack()

result_label = tk.Label(
    window,
    text="",
    font=("Arial", 12, "bold"),
    bg="#f2f2f2"
)
result_label.pack(pady=15)

window.mainloop()
```

מה השתנה:

```python
window.geometry("420x320")
```

מגדיל את החלון.

```python
window.configure(bg="#f2f2f2")
```

משנה את צבע הרקע.

```python
exit_button = tk.Button(...)
```

מוסיף כפתור יציאה.

```python
def exit_program():
    window.destroy()
```

סוגר את החלון כשלוחצים על `Exit`.

אפשר להריץ כרגיל:

```bash
py gui_version.py
```

מעולה. נמשיך עם **שלב 7: קובץ בדיקות**.

נשתמש ב־`unittest`, שהיא ספרייה מובנית בפייתון, ולכן **לא צריך להתקין שום דבר נוסף**.

בתוך תיקיית `day03`, צור קובץ חדש בשם:

```text
test_tumor_volume.py
```

ושים בו את הקוד הבא:

```python
import unittest
from tumor_volume import calculate_tumor_volume


class TestTumorVolume(unittest.TestCase):

    def test_normal_values(self):
        result = calculate_tumor_volume(10, 5)
        self.assertEqual(result, 125)

    def test_equal_length_and_width(self):
        result = calculate_tumor_volume(6, 6)
        self.assertEqual(result, 108)

    def test_decimal_values(self):
        result = calculate_tumor_volume(10.5, 5.2)
        self.assertAlmostEqual(result, 141.96)

    def test_width_greater_than_length(self):
        with self.assertRaises(ValueError):
            calculate_tumor_volume(5, 10)


if __name__ == "__main__":
    unittest.main()
```

## איך מריצים את הבדיקה

מתוך תיקיית `day03`:

```bash
py test_tumor_volume.py
```

אם הכול תקין, אתה אמור לראות משהו בסגנון:

```text
....
----------------------------------------------------------------------
Ran 4 tests in 0.001s

OK
```

הנקודות `....` אומרות ש־4 בדיקות עברו בהצלחה.

מה נבדק כאן:

```text
10, 5  → 125
6, 6   → 108
10.5, 5.2 → 141.96
5, 10 → צריך להחזיר שגיאה
```

אחרי שזה עובד, נעבור ל־**README.md**.

---

## בדיקה לשגיאה כשהוכנס `str`

נכון — כדאי להוסיף גם בדיקה למקרה שמכניסים `str`, למשל טקסט במקום מספר.

אבל יש כאן נקודה חשובה:
כרגע הפונקציה שלנו כנראה תיפול לבד אם נעביר לה טקסט, כי היא תנסה לבצע פעולה מתמטית על `str`.

לדוגמה:

```python
calculate_tumor_volume("abc", 5)
```

זה יגרום לשגיאה, אבל לא בהכרח הודעה יפה וברורה.

עדיף לשפר את הפונקציה ב־`tumor_volume.py` כך שתבדוק שהערכים מספריים.

עדכן את `tumor_volume.py` כך:

```python
def calculate_tumor_volume(length, width):
    """
    Calculate subcutaneous tumor volume in mice.

    Formula:
    Tumor Volume = (width^2 * length) / 2
    """

    if not isinstance(length, (int, float)) or not isinstance(width, (int, float)):
        raise ValueError("Length and width must be numbers.")

    if width > length:
        raise ValueError("Width cannot be greater than length.")

    return (width ** 2 * length) / 2
```

ואז תוסיף לקובץ הבדיקות `test_tumor_volume.py` בדיקה כזו:

```python
def test_string_input(self):
    with self.assertRaises(ValueError):
        calculate_tumor_volume("abc", 5)
```

אפשר גם לבדוק מצב שבו הרוחב הוא טקסט:

```python
def test_string_width(self):
    with self.assertRaises(ValueError):
        calculate_tumor_volume(10, "abc")
```

אז קובץ הבדיקות המלא יכול להיות:

```python
import unittest
from tumor_volume import calculate_tumor_volume


class TestTumorVolume(unittest.TestCase):

    def test_normal_values(self):
        result = calculate_tumor_volume(10, 5)
        self.assertEqual(result, 125)

    def test_equal_length_and_width(self):
        result = calculate_tumor_volume(6, 6)
        self.assertEqual(result, 108)

    def test_decimal_values(self):
        result = calculate_tumor_volume(10.5, 5.2)
        self.assertAlmostEqual(result, 141.96)

    def test_width_greater_than_length(self):
        with self.assertRaises(ValueError):
            calculate_tumor_volume(5, 10)

    def test_string_length(self):
        with self.assertRaises(ValueError):
            calculate_tumor_volume("abc", 5)

    def test_string_width(self):
        with self.assertRaises(ValueError):
            calculate_tumor_volume(10, "abc")


if __name__ == "__main__":
    unittest.main()
```

עכשיו יהיו לך 6 בדיקות במקום 4.
