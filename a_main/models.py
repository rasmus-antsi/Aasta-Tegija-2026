from django.db import models


class Company(models.Model):
    """Estonian Business Registry company data."""
    
    # Basic info
    name = models.CharField(max_length=500, verbose_name="Nimi")
    registry_code = models.CharField(max_length=20, unique=True, db_index=True, verbose_name="Registrikood")
    legal_form = models.CharField(max_length=100, blank=True, verbose_name="Õiguslik vorm")
    status = models.CharField(max_length=50, blank=True, verbose_name="Staatus")
    status_text = models.CharField(max_length=100, blank=True, verbose_name="Staatus tekstina")
    registered_date = models.CharField(max_length=20, blank=True, verbose_name="Registreeritud")
    
    # Location
    address = models.CharField(max_length=500, blank=True, verbose_name="Aadress")
    county = models.CharField(max_length=200, blank=True, db_index=True, verbose_name="Piirkond")
    postal_code = models.CharField(max_length=10, blank=True, verbose_name="Postiindeks")
    
    # Business activity (EMTAK)
    activity_code = models.CharField(max_length=20, blank=True, db_index=True, verbose_name="EMTAK kood")
    activity = models.CharField(max_length=500, blank=True, verbose_name="Tegevusala")
    
    # Tax info
    vat_number = models.CharField(max_length=20, blank=True, verbose_name="KMKR number")
    state_taxes = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Riiklikud maksud")
    labor_taxes = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Tööjõumaksud")
    
    # Management
    ceo = models.CharField(max_length=200, blank=True, verbose_name="Juht")
    board_members = models.TextField(blank=True, verbose_name="Juhatuse liikmed")
    
    # Financial data
    employees = models.FloatField(null=True, blank=True, db_index=True, verbose_name="Töötajaid")
    revenue = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, db_index=True, verbose_name="Käive")
    profit = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Kasum")
    report_year = models.CharField(max_length=4, blank=True, verbose_name="Aruande aasta")
    
    # Links
    registry_link = models.URLField(max_length=500, blank=True, verbose_name="Registri link")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ettevõte"
        verbose_name_plural = "Ettevõtted"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.registry_code})"
    
    def get_board_members_list(self):
        """Return board members as a list."""
        if self.board_members:
            return [m.strip() for m in self.board_members.split(',')]
        return []
    
    @classmethod
    def get_complete_companies(cls):
        """Get companies with all required fields filled."""
        return cls.objects.exclude(
            name='',
        ).exclude(
            registry_code='',
        ).exclude(
            legal_form='',
        ).exclude(
            registered_date='',
        ).exclude(
            county='',
        ).exclude(
            activity='',
        ).exclude(
            ceo='',
        ).exclude(
            board_members='',
        ).filter(
            employees__isnull=False,
            revenue__isnull=False,
            profit__isnull=False,
            labor_taxes__isnull=False,
        )
