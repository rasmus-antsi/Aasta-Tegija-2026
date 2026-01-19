"""
Majandusmäng - Estonian Business Quiz Game
"""
import random
from datetime import datetime
from decimal import Decimal
from django.shortcuts import render, redirect
from django.db.models import Q
from .models import Company


# Game configuration
PROMO_THRESHOLD = 5  # Show promo code at 5 points
TYPE_COOLDOWN = 5  # Same question type can't repeat for 5 questions
COMPANY_COOLDOWN = 2  # Same company can't repeat for 2 questions

# Minimum differences for fair questions
MIN_DIFF = {
    'years': 7,
    'employees': 20,
    'revenue': Decimal('2000000'),  # 2M euros
    'profit': Decimal('500000'),  # 500K euros
    'labor_taxes': Decimal('100000'),  # 100K euros
}

# Question types
QUESTION_TYPES = [
    'age',           # Which company is older
    'employees',     # Which has more employees
    'revenue',       # Which has higher revenue
    'profit',        # Which has higher profit
    'labor_taxes',   # Which has higher labor costs
    'county',        # Which company is in [county]
    'ceo',           # Which company is led by [CEO]
    'activity',      # Which company does [activity]
    'legal_form',    # Which is OÜ/AS/MTÜ
    'vat',           # Which has VAT number
]


def get_complete_companies():
    """Get queryset of companies with all fields populated."""
    return Company.objects.exclude(
        name=''
    ).exclude(
        registry_code=''
    ).exclude(
        legal_form=''
    ).exclude(
        registered_date=''
    ).exclude(
        county=''
    ).exclude(
        activity=''
    ).exclude(
        ceo=''
    ).filter(
        employees__isnull=False,
        revenue__isnull=False,
        profit__isnull=False,
        labor_taxes__isnull=False,
    ).exclude(
        vat_number=''
    )


def parse_date(date_str):
    """Parse Estonian date format DD.MM.YYYY to datetime."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%d.%m.%Y')
    except ValueError:
        return None


def get_year_from_date(date_str):
    """Extract year from date string."""
    dt = parse_date(date_str)
    return dt.year if dt else None


def extract_county_name(county_str):
    """Extract county name from county field.
    
    Format is typically: "address, city, COUNTY maakond"
    Returns normalized county name (e.g., 'harju' from 'Harju maakond')
    """
    if not county_str:
        return None
    # Extract the last part after final comma (the county)
    parts = [p.strip() for p in county_str.split(',')]
    if not parts:
        return None
    
    # Get the last part which should be "COUNTY maakond"
    county_part = parts[-1]
    # Remove "maakond" suffix and normalize
    county = county_part.replace(' maakond', '').strip().lower()
    return county if county else None


def get_available_question_types(recent_types):
    """Get question types not in recent cooldown."""
    available = [t for t in QUESTION_TYPES if t not in recent_types[-TYPE_COOLDOWN:]]
    return available if available else QUESTION_TYPES


def get_companies_for_question(q_type, recent_company_ids):
    """Get two suitable companies for a question type."""
    
    # Base queryset - only complete companies, exclude recent ones
    base_qs = get_complete_companies().exclude(id__in=recent_company_ids[-COMPANY_COOLDOWN:])
    
    if q_type == 'age':
        # Need companies with valid dates, 7+ years apart
        companies = list(base_qs.exclude(registered_date='').order_by('?')[:500])
        random.shuffle(companies)
        
        for c1 in companies:
            year1 = get_year_from_date(c1.registered_date)
            if not year1:
                continue
            for c2 in companies:
                if c1.id == c2.id:
                    continue
                year2 = get_year_from_date(c2.registered_date)
                if year2 and abs(year1 - year2) >= MIN_DIFF['years']:
                    return (c1, c2) if year1 < year2 else (c2, c1)  # older first
        return None
    
    elif q_type == 'employees':
        # Need companies with employee data, 20+ difference
        companies = list(base_qs.filter(employees__isnull=False).order_by('?')[:500])
        random.shuffle(companies)
        
        for c1 in companies:
            for c2 in companies:
                if c1.id == c2.id:
                    continue
                if c1.employees is not None and c2.employees is not None:
                    diff = abs(c1.employees - c2.employees)
                    if diff >= MIN_DIFF['employees']:
                        return (c1, c2) if c1.employees > c2.employees else (c2, c1)
        return None
    
    elif q_type == 'revenue':
        companies = list(base_qs.filter(revenue__isnull=False).order_by('?')[:500])
        random.shuffle(companies)
        
        for c1 in companies:
            for c2 in companies:
                if c1.id == c2.id:
                    continue
                if c1.revenue is not None and c2.revenue is not None:
                    diff = abs(c1.revenue - c2.revenue)
                    if diff >= MIN_DIFF['revenue']:
                        return (c1, c2) if c1.revenue > c2.revenue else (c2, c1)
        return None
    
    elif q_type == 'profit':
        companies = list(base_qs.filter(profit__isnull=False).order_by('?')[:500])
        random.shuffle(companies)
        
        for c1 in companies:
            for c2 in companies:
                if c1.id == c2.id:
                    continue
                if c1.profit is not None and c2.profit is not None:
                    diff = abs(c1.profit - c2.profit)
                    if diff >= MIN_DIFF['profit']:
                        return (c1, c2) if c1.profit > c2.profit else (c2, c1)
        return None
    
    elif q_type == 'labor_taxes':
        companies = list(base_qs.filter(labor_taxes__isnull=False).order_by('?')[:500])
        random.shuffle(companies)
        
        for c1 in companies:
            for c2 in companies:
                if c1.id == c2.id:
                    continue
                if c1.labor_taxes is not None and c2.labor_taxes is not None:
                    diff = abs(c1.labor_taxes - c2.labor_taxes)
                    if diff >= MIN_DIFF['labor_taxes']:
                        return (c1, c2) if c1.labor_taxes > c2.labor_taxes else (c2, c1)
        return None
    
    elif q_type == 'county':
        # Find two companies in different counties
        companies = list(base_qs.exclude(county='').order_by('?')[:500])
        random.shuffle(companies)
        
        for c1 in companies:
            county1 = extract_county_name(c1.county)
            if not county1:
                continue
            for c2 in companies:
                if c1.id == c2.id:
                    continue
                county2 = extract_county_name(c2.county)
                if county2 and county1 != county2:
                    return (c1, c2)  # c1 is correct (has the county we'll ask about)
        return None
    
    elif q_type == 'ceo':
        # Find two companies with different CEOs
        companies = list(base_qs.exclude(ceo='').order_by('?')[:500])
        random.shuffle(companies)
        
        for c1 in companies:
            for c2 in companies:
                if c1.id == c2.id:
                    continue
                if c1.ceo != c2.ceo:
                    return (c1, c2)
        return None
    
    elif q_type == 'activity':
        # Find two companies with different activities
        companies = list(base_qs.exclude(activity='').order_by('?')[:500])
        random.shuffle(companies)
        
        for c1 in companies:
            for c2 in companies:
                if c1.id == c2.id:
                    continue
                if c1.activity != c2.activity:
                    return (c1, c2)
        return None
    
    elif q_type == 'legal_form':
        # Find two companies with different legal forms
        companies = list(base_qs.exclude(legal_form='').order_by('?')[:500])
        random.shuffle(companies)
        
        for c1 in companies:
            for c2 in companies:
                if c1.id == c2.id:
                    continue
                if c1.legal_form != c2.legal_form:
                    return (c1, c2)
        return None
    
    elif q_type == 'vat':
        # One with VAT, one without
        c1 = base_qs.exclude(vat_number='').order_by('?').first()
        if not c1:
            return None
        c2 = base_qs.filter(vat_number='').order_by('?').first()
        if not c2:
            return None
        return (c1, c2)
    
    return None


def generate_question_text(q_type, correct_company):
    """Generate the question text with answer embedded in question."""
    
    if q_type == 'age':
        year = get_year_from_date(correct_company.registered_date)
        if year:
            return f"Milline ettevõte asutati aastal {year}?"
        return "Milline ettevõte on vanem?"
    
    elif q_type == 'employees':
        employees = int(correct_company.employees)
        return f"Millisel ettevõttel on {employees} töötajat?"
    
    elif q_type == 'revenue':
        revenue = int(correct_company.revenue)
        # Format large numbers nicely
        if revenue >= 1000000:
            revenue_str = f"{revenue / 1000000:.1f} miljonit"
        elif revenue >= 1000:
            revenue_str = f"{revenue / 1000:.0f} tuhat"
        else:
            revenue_str = str(revenue)
        return f"Millisel ettevõttel on käive {revenue_str} eurot?"
    
    elif q_type == 'profit':
        profit = int(correct_company.profit)
        if profit >= 1000000:
            profit_str = f"{profit / 1000000:.1f} miljonit"
        elif profit >= 1000:
            profit_str = f"{profit / 1000:.0f} tuhat"
        else:
            profit_str = str(profit)
        return f"Millisel ettevõttel on kasum {profit_str} eurot?"
    
    elif q_type == 'labor_taxes':
        labor_taxes = int(correct_company.labor_taxes)
        if labor_taxes >= 1000000:
            taxes_str = f"{labor_taxes / 1000000:.1f} miljonit"
        elif labor_taxes >= 1000:
            taxes_str = f"{labor_taxes / 1000:.0f} tuhat"
        else:
            taxes_str = str(labor_taxes)
        return f"Millisel ettevõttel on tööjõukulud {taxes_str} eurot?"
    
    elif q_type == 'county':
        # Extract county name using our helper function
        county_name = extract_county_name(correct_company.county)
        if county_name:
            # Capitalize first letter for display
            county_display = county_name.capitalize() + " maakond"
        else:
            county_display = correct_company.county.split(',')[-1].strip() if correct_company.county else "?"
        return f"Milline ettevõte asub {county_display}?"
    
    elif q_type == 'ceo':
        return f"Millist ettevõtet juhib {correct_company.ceo}?"
    
    elif q_type == 'activity':
        activity = correct_company.activity[:60] + "..." if len(correct_company.activity) > 60 else correct_company.activity
        return f"Milline ettevõte tegeleb: {activity}?"
    
    elif q_type == 'legal_form':
        return f"Milline ettevõte on {correct_company.legal_form}?"
    
    elif q_type == 'vat':
        return f"Millisel ettevõttel on KMKR number {correct_company.vat_number}?"
    
    return "Vali õige ettevõte"


def generate_question(session):
    """Generate a new question and store in session."""
    recent_types = session.get('recent_types', [])
    recent_company_ids = session.get('recent_company_ids', [])
    
    # Get available question types
    available_types = get_available_question_types(recent_types)
    random.shuffle(available_types)
    
    # Try each type until we find valid companies
    for q_type in available_types:
        result = get_companies_for_question(q_type, recent_company_ids)
        if result:
            correct_company, wrong_company = result
            
            # Randomly position correct answer (left or right)
            if random.choice([True, False]):
                company_a, company_b = correct_company, wrong_company
                correct_position = 'a'
            else:
                company_a, company_b = wrong_company, correct_company
                correct_position = 'b'
            
            # Generate question text
            question_text = generate_question_text(q_type, correct_company)
            
            # Update session
            recent_types.append(q_type)
            recent_company_ids.extend([correct_company.id, wrong_company.id])
            
            # Keep only recent items
            session['recent_types'] = recent_types[-TYPE_COOLDOWN:]
            session['recent_company_ids'] = recent_company_ids[-COMPANY_COOLDOWN * 2:]
            
            # Store current question
            session['current_question'] = {
                'type': q_type,
                'text': question_text,
                'company_a_id': company_a.id,
                'company_b_id': company_b.id,
                'correct_position': correct_position,
                'correct_company_id': correct_company.id,
            }
            
            return {
                'text': question_text,
                'company_a': company_a,
                'company_b': company_b,
            }
    
    # Fallback - shouldn't happen with enough data
    return None


def index(request):
    """Main game view."""
    
    # Initialize session if needed
    if 'score' not in request.session:
        request.session['score'] = 0
        request.session['recent_types'] = []
        request.session['recent_company_ids'] = []
        request.session['current_question'] = None
        request.session['feedback'] = None
        request.session['promo_shown'] = False
    
    feedback = request.session.get('feedback')
    show_promo = False
    
    # If continuing after promo, clear feedback to generate new question
    if request.GET.get('continue') == '1':
        request.session['feedback'] = None
        feedback = None
        request.session.modified = True
    
    context = {
        'score': request.session['score'],
        'points_to_win': PROMO_THRESHOLD,
        'feedback': feedback,
        'game_over': False,
    }
    
    # Handle answer submission
    if request.method == 'POST':
        answer = request.POST.get('answer')  # 'a' or 'b'
        current_q = request.session.get('current_question')
        
        if current_q and answer:
            correct = answer == current_q['correct_position']
            old_score = request.session['score']
            
            if correct:
                request.session['score'] += 1
                request.session['feedback'] = {
                    'correct': True,
                    'selected': answer,
                    'correct_position': current_q['correct_position'],
                }
            else:
                # Wrong answer = -1 point
                request.session['score'] -= 1
                request.session['feedback'] = {
                    'correct': False,
                    'selected': answer,
                    'correct_position': current_q['correct_position'],
                }
            
            # Check if should show promo (hit 5 points for first time)
            if request.session['score'] >= PROMO_THRESHOLD and not request.session.get('promo_shown', False):
                request.session['show_promo'] = True
                request.session['promo_shown'] = True
            
            request.session.modified = True
            return redirect('index')
    
    # If showing feedback, display the same question with the same companies
    if feedback:
        current_q = request.session.get('current_question')
        if current_q:
            context['question'] = current_q['text']
            try:
                company_a = Company.objects.get(id=current_q['company_a_id'])
                company_b = Company.objects.get(id=current_q['company_b_id'])
                context['company_a'] = company_a
                context['company_b'] = company_b
            except Company.DoesNotExist:
                pass
        
        # Check if should show promo popup
        if request.session.get('show_promo', False):
            context['show_promo'] = True
            request.session['show_promo'] = False
        
        # Update score in context
        context['score'] = request.session['score']
        
        # Clear feedback for next request
        request.session['feedback'] = None
        request.session.modified = True
        return render(request, 'a_main/index.html', context)
    
    # Generate new question
    question = generate_question(request.session)
    
    if question:
        context['question'] = question['text']
        context['company_a'] = question['company_a']
        context['company_b'] = question['company_b']
    else:
        context['error'] = 'Ei suutnud küsimust genereerida. Proovi uuesti.'
    
    request.session.modified = True
    return render(request, 'a_main/index.html', context)


def reset_game(request):
    """Reset the game state."""
    request.session['score'] = 0
    request.session['recent_types'] = []
    request.session['recent_company_ids'] = []
    request.session['current_question'] = None
    request.session['feedback'] = None
    request.session['promo_shown'] = False
    request.session['show_promo'] = False
    request.session.modified = True
    return redirect('index')
