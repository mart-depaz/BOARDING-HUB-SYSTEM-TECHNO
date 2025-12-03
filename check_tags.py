import re

files = [
    'templates/students/owner_dashboard_students.html',
    'templates/students/layout_students.html',
    'templates/students/partials/my_home_posts_students.html',
    'templates/students/partials/my_home_boarders_students.html',
    'templates/students/partials/my_home_payments_students.html',
    'templates/students/partials/my_home_messenger_students.html',
]

for file in files:
    try:
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()
            ifs = len(re.findall(r'\{%\s*if\s', content))
            endifs = len(re.findall(r'\{%\s*endif\s*%\}', content))
            print(f'{file}:')
            print(f'  if: {ifs}, endif: {endifs}, balanced: {ifs == endifs}')
    except Exception as e:
        print(f'{file}: ERROR - {e}')
