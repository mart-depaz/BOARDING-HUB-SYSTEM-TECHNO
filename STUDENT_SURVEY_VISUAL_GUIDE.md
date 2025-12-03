# Student Survey Display - Visual Guide

## Current Database State

```
Admin 1 (surigaodelnortestateuniversity@ssct.edu.ph)
└─ School: "Surigao Del Norte State University - Main Campus"
   ├─ Survey ID 6: "Student Registration Survey" (ACTIVE)
   ├─ Survey ID 3: "Student Registration Survey" (ACTIVE)
   ├─ Survey ID 5: "Student Registration Survey" (CLOSED)
   ├─ Survey ID 4: "Student Registration Survey" (CLOSED)
   ├─ Survey ID 2: "Property Survey" (CLOSED)
   └─ Survey ID 1: "Student Registration Survey" (CLOSED)

Admin 2 (llarong1@ssct.edu.ph)
└─ School: "Surigao del Norte State University"
   └─ Survey ID 8: "Student Registration Survey" (ACTIVE)

Students (both in Admin 1's school):
├─ mobjhon96@gmail.com → School: "Surigao Del Norte State University - Main Campus"
└─ jhayr1@gmail.com → School: "Surigao Del Norte State University - Main Campus"
```

## What Students See When They Visit "Admin Surveys"

```
╔════════════════════════════════════════════════════════════════════════╗
║                        ADMIN SCHOOL SURVEYS                           ║
║  Complete surveys from your school to stay registered and compliant   ║
╚════════════════════════════════════════════════════════════════════════╝

┌─ AVAILABLE SURVEYS COUNTER ─────────────────────────────────────────────┐
│  Available Surveys: 3     Status: Pending     Last Updated: [date]      │
└────────────────────────────────────────────────────────────────────────┘

┌─ SURVEY CARD 1 ─────────────────────────────────────────────────────────┐
│ ╔─ CYAN BORDER ───────────────────────────────────────────────────────╗ │
│ ║ 🔴 "Student Registration Survey"     [🔴 REQUIRED]                 ║ │
│ ║                                                                    ║ │
│ ║ 📌 School: Surigao Del Norte State University - Main Campus       ║ │
│ ║                                                                    ║ │
│ ║ [Survey description here]                                         ║ │
│ ║                                                                    ║ │
│ ║ [Category] [ACTIVE] [ID: 6]                [Take Survey Button]  ║ │
│ ╚────────────────────────────────────────────────────────────────────╝ │
└────────────────────────────────────────────────────────────────────────┘

┌─ SURVEY CARD 2 ─────────────────────────────────────────────────────────┐
│ ╔─ CYAN BORDER ───────────────────────────────────────────────────────╗ │
│ ║ 🔴 "Student Registration Survey"     [🔴 REQUIRED]                 ║ │
│ ║                                                                    ║ │
│ ║ 📌 School: Surigao Del Norte State University - Main Campus       ║ │
│ ║                                                                    ║ │
│ ║ [Survey description here]                                         ║ │
│ ║                                                                    ║ │
│ ║ [Category] [ACTIVE] [ID: 3]                [Take Survey Button]  ║ │
│ ╚────────────────────────────────────────────────────────────────────╝ │
└────────────────────────────────────────────────────────────────────────┘

┌─ SURVEY CARD 3 ─────────────────────────────────────────────────────────┐
│ ╔─ YELLOW BORDER ─────────────────────────────────────────────────────╗ │
│ ║ 🟡 "Student Registration Survey"    [🟡 Optional for you]          ║ │
│ ║                                                                    ║ │
│ ║ 📌 School: Surigao del Norte State University                      ║ │
│ ║                                                                    ║ │
│ ║ [Survey description here]                                         ║ │
│ ║                                                                    ║ │
│ ║ [Category] [ACTIVE] [ID: 8]                [Take Survey Button]  ║ │
│ ╚────────────────────────────────────────────────────────────────────╝ │
└────────────────────────────────────────────────────────────────────────┘
```

## Color Legend

### 🔴 RED Badge "REQUIRED"
- **Meaning**: This survey is from YOUR school. You should complete it.
- **Border**: Cyan (bright cyan)
- **Background**: Dark with cyan accents
- **Action**: Students should take this survey

### 🟡 YELLOW Badge "Optional for you"
- **Meaning**: This survey is from another school. You don't need to complete it, but you can view it for reference.
- **Border**: Yellow (muted yellow)
- **Background**: Dark with yellow accents
- **Action**: Optional to complete

## Key Information Displayed

For **each survey**, students see:

1. **Survey Title** (e.g., "Student Registration Survey")
2. **Status Badge**
   - 🔴 REQUIRED (for your school)
   - 🟡 Optional for you (for other schools)
3. **School Name** (📌 clearly labeled)
4. **Survey Description**
5. **Category Tag**
6. **Status** (Active/Closed)
7. **Survey ID**
8. **Take Survey Button**

## What This Solves

### Before
```
Student saw only surveys from Admin 1's school
→ Missing surveys from Admin 2
→ Confusion about why certain surveys weren't available
```

### After
```
Student sees ALL surveys
→ Required ones from their school are clearly marked 🔴
→ Optional ones from other schools are clearly marked 🟡
→ School name shown for each survey
→ Clear understanding of what they need to do
```

## Student Workflow

1. Student logs in
2. Navigates to "Admin Surveys"
3. Sees all active surveys (both admins)
4. **Identify Required Surveys** (look for red badges and cyan borders)
5. **Complete Required Surveys** (from their school)
6. **Optional Review** (can look at yellow ones for reference)
7. All surveys completed → Status shows "No Surveys" or "Pending" is cleared

## Admin Perspective

### Admin 1 (Main Campus)
- Creates survey in their school
- Students from Main Campus see it as 🔴 REQUIRED
- Students from other schools see it as 🟡 Optional
- All students receive the survey

### Admin 2 (Other Campus)
- Creates survey in their school
- Students from their school see it as 🔴 REQUIRED
- Students from Main Campus see it as 🟡 Optional
- All students receive the survey

## Benefits

✅ **No confusion**: Students know which surveys apply to them
✅ **Complete visibility**: Students see everything available
✅ **Clear priorities**: Red = must do, Yellow = for info
✅ **School context**: Each survey shows its origin school
✅ **Multi-admin support**: Multiple admins can coexist without conflicts
✅ **Professional UI**: Color-coded, well-organized interface

---

**Result**: Students from BOTH schools see BOTH admins' surveys with clear visual indicators of which ones they need to complete.
