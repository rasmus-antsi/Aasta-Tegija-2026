# Majandusmäng - Estonian Business Quiz Game

A fun, interactive quiz game that tests your knowledge of Estonian businesses. Answer questions about companies from the Estonian Business Register and earn points to unlock rewards!

## Features

- 🎮 **Interactive Quiz Game**: Answer questions about Estonian businesses
- 📊 **Real Business Data**: Uses data from the Estonian Business Register (Ariregister)
- 🎯 **Score System**: Earn points for correct answers, lose points for wrong ones
- 🎁 **Rewards**: Collect 5 points to unlock a special discount code
- 🎨 **Modern UI**: Dark theme with smooth animations and premium UX
- 📱 **Responsive Design**: Works on desktop and mobile devices

## Game Mechanics

- **Scoring**: 
  - Correct answer: +1 point
  - Wrong answer: -1 point
  - Score can go negative
  
- **Questions**: Questions include the answer directly (e.g., "Which company was founded in 1995?")
- **Question Types**:
  - Company age (founding year)
  - Number of employees
  - Revenue
  - Profit
  - Labor costs
  - County location
  - CEO name
  - Business activity
  - Legal form
  - VAT number

- **Auto-advance**: After answering, the game automatically moves to the next question after 2 seconds

## Data Source

The game uses open data from the Estonian Business Register:
- Basic company information
- Management data (CEO, board members)
- Financial reports (revenue, profit, employees)
- EMTAK activity codes

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd aasta_tegija_2025
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run migrations:
```bash
python manage.py migrate
```

5. Import company data:
```bash
python manage.py import_companies
```

6. Run the development server:
```bash
python manage.py runserver
```

7. Open your browser and navigate to `http://127.0.0.1:8000`

## Configuration

### Game Settings
- `PROMO_THRESHOLD`: Points needed to unlock reward (default: 5)
- `TYPE_COOLDOWN`: Same question type can't repeat for N questions (default: 5)
- `COMPANY_COOLDOWN`: Same company can't repeat for N questions (default: 2)

### Minimum Differences
To ensure fair questions, companies must meet minimum differences:
- Age: 7+ years apart
- Employees: 20+ difference
- Revenue: 2M+ euros difference
- Profit: 500K+ euros difference
- Labor taxes: 100K+ euros difference

## Project Structure

```
aasta_tegija_2025/
├── _core/              # Django project settings
├── a_main/             # Main app
│   ├── models.py       # Company model
│   ├── views.py        # Game logic
│   ├── urls.py         # URL routing
│   └── management/     # Management commands
│       └── commands/
│           └── import_companies.py
├── templates/          # HTML templates
│   └── a_main/
│       └── index.html  # Main game template
├── static/             # Static files (CSS)
├── utils/              # Utility scripts
│   └── scraper.py      # Data import from Ariregister
└── manage.py          # Django management script
```

## Technologies Used

- **Backend**: Django 6.0
- **Frontend**: HTML, CSS (Tailwind CSS), JavaScript
- **Icons**: Lucide Icons
- **Database**: SQLite (default)

## License

This project is for educational purposes.

## Credits

- Data source: Estonian Business Register (ariregister.rik.ee)
- Built with Django and modern web technologies
