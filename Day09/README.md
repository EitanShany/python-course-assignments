# Day09 — Pima Indians Diabetes Prediction

Dataset: Pima Indians Diabetes
- Source: public raw CSV mirror for reproducible examples
- CSV URL: https://raw.githubusercontent.com/jbrownlee/Datasets/master/pima-indians-diabetes.data.csv
- Size: 768 rows, 8 features + target

מטרה:
- לבנות דוגמת ניבוי ביולוגית שניתנת לשחזור בקלות, כולל הורדת נתונים, אימון מודל סיווג, ושימוש במודל להערכת סיכון.

קבצים עיקריים:
- `data_download.py` — מוריד את ה־CSV לתיקייה `data/`.
- `train_model.py` — מאמן מודל סיווג ושומר אותו ב־`models/`.
- `predict_example.py` — טוען את המודל ומריץ דוגמת חיזוי.
- `visualize.py` — מציג גרף של אוכלוסיות לפי שדות Glucose ו־BMI.
- `gui.py` — ממשק גרפי לטעינת דוגמאות נוספות, צפייה בגרפים ושמירה שלהם.
- הממשק כולל גם גרף UMAP דו-ממדי לאחר נרמול התכונות.
- `requirements.txt` — תלותיות.
- `prompts.txt` — הפקודות ששאלנו את ChatGPT.

הרצה מהירה:
1. צרו סביבת וירטואלית והתקינו דרישות:
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r Day09/requirements.txt
```
2. הורידו את הנתונים:
```bash
python Day09/data_download.py
```
3. אימנו את המודלים:
```bash
python Day09/train_model.py
```
4. הריצו דוגמת חיזוי:
```bash
python Day09/predict_example.py
```
5. ראו את האוכלוסיות באופן חזותי:
```bash
python Day09/visualize.py
```
6. פתחו את הממשק הגרפי:
```bash
python Day09/gui.py
```

הערות לשחזור:
- קבצי המודל יהיו ב־`Day09/models/`.
- הקוד משתמש ב־`pima-indians-diabetes.csv` עם 8 תכונות.

Prompts (כולל קובץ מלא ב־`prompts.txt`).

**לוגיקות עסקיות מוצעות (2-3):**

- **Risk Scoring (דירוג סיכון):**
  תיאור: חישוב הסתברות לפיתוח סוכרת עבור מטופל בהתבסס על מדדי בריאות מוקדמים. שימוש: לזהות מטופלים בסיכון גבוה לקבלת מעקב מוקדם ותכניות מניעה.
  החלטה עסקית: ייעול שימוש בצוות רפואי בכך שמטופלים בסיכון גבוה יקבלו טיפול מונע מיידי.

- **Prevention Targeting (מיקוד מניעה):**
  תיאור: סיווג מטופלים לשתי קטגוריות — גבוה/נמוך סיכון — כדי לתעדף התערבויות תזונתיות ופעילות גופנית.
  החלטה עסקית: לצמצם עלויות בריאות על ידי מתן תכניות מניעה לאוכלוסייה עם סיכון גבוה בלבד.

- **Resource Prioritization (תעדוף משאבים):**
  תיאור: שימוש בחיזוי כדי להחליט אילו מטופלים צריכים בדיקות נוספות, הדרכה אישית או מעקב קליני. שימוש: הפחתת עומס על מרכזי בריאות.
  החלטה עסקית: חלוקה יעילה של משאבים לשירותים רפואיים ומניעת אשפוזים מיותרים.

אם תרצו, אוכל:
- להוסיף קובץ `test_*.py` ובדיקות פשוטות.
- להשתמש ב־`GridSearchCV` לשיפור המודל.
- להכניס דוגמאות של כניסת JSON ל־`predict_example.py`.
