# Survey Visibility Fix - Multi-Admin Support

## Problem Statement
You have 2 different admin accounts managing surveys in different schools:
- **Admin 1** (`surigaodelnortestateuniversity@ssct.edu.ph`) - School: "Surigao Del Norte State University - Main Campus"
- **Admin 2** (`llarong1@ssct.edu.ph`) - School: "Surigao del Norte State University"

Students were only seeing surveys from Admin 1's school because the system filtered surveys by the student's school. This prevented Admin 2's surveys from being visible to students.

## Solution Implemented

### 1. Updated Backend Logic (`students/views.py`)

**Changed Survey Query:**
- **Before**: Only showed surveys from the student's specific school
- **After**: Shows ALL active surveys from ANY school

**Added "Required" Flag Logic:**
- For each survey, added an `is_required` flag
- `is_required = True` only if the survey's school matches the student's school
- Students can see all surveys but know which ones apply to them

**Code Changes (lines 109-133):**
```python
# Fetch surveys from ALL schools (so all students see all surveys)
from core.models import Survey
surveys = []
pending_surveys = 0
try:
    student = request.user.student_profile
    # Get ALL active surveys for students or both recipients
    all_surveys = Survey.objects.filter(
        status='active',
        recipient_type__in=['students', 'both']  # Show surveys for students or both
    ).order_by('-created_at')
    
    # Add a flag indicating if this survey is REQUIRED for this student
    # (only required if the survey's school matches the student's school)
    surveys = []
    for survey in all_surveys:
        is_required = survey.school == student.school if student.school else False
        surveys.append({
            'survey': survey,
            'is_required': is_required,
            'school_name': survey.school.name if survey.school else 'Unknown School'
        })
    
    pending_surveys = len(surveys)
except Exception:
    surveys = []
    pending_surveys = 0
```

### 2. Updated Template (`templates/students/owner_dashboard_students.html`)

**Enhanced Survey Display (lines 141-167):**
- Shows ALL surveys from all schools
- **Indicates which school each survey is from** (📌 School: [school name])
- **Mark required surveys with RED badge**: "REQUIRED" - for student's school
- **Mark optional surveys with YELLOW badge**: "Optional for you" - for other schools
- **Color-coded borders**: 
  - Cyan border for required surveys
  - Yellow border for optional surveys

**Template Changes:**
```html
{% for survey_item in surveys %}
{% with survey=survey_item.survey is_required=survey_item.is_required school_name=survey_item.school_name %}
<div class="rounded-2xl border {% if is_required %}border-neon-cyan/60{% else %}border-neon-yellow/40{% endif %} bg-white/5 p-6 hover:bg-white/10 transition cursor-pointer" onclick="window.location.href='/survey/{{ survey.unique_code }}/'">
    <div class="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
        <div class="flex-1">
            <div class="flex items-center gap-2 mb-2">
                <h4 class="text-lg font-bold text-neon-cyan">{{ survey.title }}</h4>
                {% if is_required %}
                <span class="px-2 py-1 rounded-full bg-neon-red/20 border border-neon-red/60 text-neon-red text-xs font-bold">REQUIRED</span>
                {% else %}
                <span class="px-2 py-1 rounded-full bg-neon-yellow/20 border border-neon-yellow/60 text-neon-yellow text-xs font-semibold">Optional for you</span>
                {% endif %}
            </div>
            <p class="text-xs text-neon-yellow/80 mb-2">📌 School: {{ school_name }}</p>
            <!-- Rest of survey details -->
```

## How It Works Now

### For Students
1. When you visit the "Admin Surveys" section, you see **ALL active surveys** from all schools
2. **Required surveys** (from your school) have:
   - Red "REQUIRED" badge
   - Cyan border
   - Clear indication this applies to you
3. **Optional surveys** (from other schools) have:
   - Yellow "Optional for you" badge
   - Yellow border
   - Clear indication this is informational only
4. Each survey clearly shows which school it's from

### For Admins
- Admin 1 can create surveys in "Surigao Del Norte State University - Main Campus"
- Admin 2 can create surveys in "Surigao del Norte State University"
- Both admins' surveys appear to all students
- Students from each school know which surveys they must complete

## Database Queries

**All active surveys visible to students:**
```
Survey.objects.filter(
    status='active',
    recipient_type__in=['students', 'both']
).order_by('-created_at')
```

**No school filtering** - this allows all students to see all surveys

## Visual Indicators

| Survey Type | Badge Color | Border Color | Indicator |
|------------|-------------|-------------|-----------|
| Required (Your School) | 🔴 Red | Cyan | REQUIRED |
| Optional (Other School) | 🟡 Yellow | Yellow | Optional for you |

## Testing

To verify the changes:
1. Log in as a student
2. Go to "Admin Surveys" section
3. You should see surveys from both Admin 1 and Admin 2
4. Surveys from your school are marked "REQUIRED"
5. Surveys from other schools are marked "Optional for you"
6. Each survey shows the school name it belongs to

## Files Modified

1. **`students/views.py`** - Updated survey query logic (lines 109-133)
2. **`templates/students/owner_dashboard_students.html`** - Updated survey display template (lines 141-167)

## No Database Changes Required

This implementation does NOT require:
- New migrations
- New model fields
- Changes to existing surveys

The logic is purely in the view and template layers.
