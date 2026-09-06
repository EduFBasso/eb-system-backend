# backend/apps/authentication/models/register_models.py
from phonenumber_field.modelfields import PhoneNumberField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone


class ProfessionalManager(BaseUserManager):
    """
    Gerenciador customizado para a criação de instâncias de Profissionais/Usuários.
    Garante o fluxo correto de criação de usuários com senha utilizável.
    """
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("O e-mail é obrigatório para cadastro.")

        email = self.normalize_email(email)
        extra_fields.setdefault("is_staff", False)       
        extra_fields.setdefault("is_superuser", False)   

        user = self.model(email=email, **extra_fields)

        if password:
            user.set_password(password)  
        else:
            user.set_unusable_password() 

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class Professional(AbstractBaseUser, PermissionsMixin):
    """
    [SOLID - Single Responsibility Principle]
    Esta classe é o modelo de Usuário Customizado (Auth User) unificado do sistema.
    Representa a identidade de qualquer profissional ou administrador na plataforma.
    O controle de quais clínicas este usuário gerencia ocorre via TenantMembership.
    """
    first_name = models.CharField("Nome", max_length=50)
    last_name = models.CharField("Sobrenome", max_length=70)
    display_name = models.CharField(
        "Nome de exibição",
        max_length=100,
        blank=True,
        help_text="Como os clientes o conhecem visualmente nas notificações: ex. 'Podóloga Regiane'.",
    )
    phone = PhoneNumberField(
        "Telefone Celular",
        region="BR",
        blank=False,
        null=False,
        help_text="Obrigatório para ativação e recebimento de notificações via Telegram. Ex: (19) 99855-2882 ou 19998552882.",
    ) 
    email = models.EmailField("E-mail corporativo", unique=True)

    register_number = models.CharField(
        "Registro Profissional (CRM/CRBM)", 
        max_length=30, 
        unique=True,
        blank=True,
        null=True
    )
    specialty = models.CharField("Especialidade Atendida", max_length=100, blank=True)
    can_manage_professionals = models.BooleanField(
        default=False,
        verbose_name="Pode gerenciar profissionais / Admin global"
    )
    
    UI_THEME_CHOICES = (
        ("blue", "Azul"),
        ("green", "Verde"),
        ("pink", "Rosa"),
    )
    ui_theme = models.CharField(
        "Tema visual do Painel",
        max_length=10,
        choices=UI_THEME_CHOICES,
        default="blue",
    )
    lock_odonto_plan_after_print = models.BooleanField(
        "Bloquear plano odontológico após impressão",
        default=True,
        help_text="Quando ativo, a impressão de um plano odontológico bloqueia novas edições.",
    )
    odonto_quote_validity_days = models.PositiveSmallIntegerField(
        "Validade do orçamento odontológico (dias)",
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
        help_text="Prazo exibido nos orçamentos odontológicos impressos.",
    )

    city = models.CharField("Cidade", max_length=50, blank=True)
    state = models.CharField("Estado", max_length=2, blank=True)
    address = models.CharField("Endereço comercial", max_length=160, blank=True)
    number = models.CharField("Número", max_length=20, blank=True)
    neighborhood = models.CharField("Bairro", max_length=80, blank=True)
    zip_code = models.CharField("CEP", max_length=9, blank=True)
    cnpj = models.CharField("CNPJ", max_length=18, blank=True)

    is_staff = models.BooleanField("Acesso ao Django Admin", default=False)
    is_active = models.BooleanField("Usuário Ativo no Sistema", default=True)
    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    deactivated_at = models.DateTimeField("Desativado em", null=True, blank=True)
    deactivation_reason = models.CharField(
        "Motivo do Desligamento", max_length=120, blank=True
    )

    objects = ProfessionalManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        app_label = 'authentication'
        verbose_name = "Profissional"
        verbose_name_plural = "Profissionais"

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

    def deactivate(self, reason: str = ""):
        """Soft delete amigável para preservar o histórico médico passado do profissional."""
        if not self.deactivated_at:
            self.deactivated_at = timezone.now()
        if reason:
            self.deactivation_reason = reason[:120]
        self.is_active = False
        self.save(update_fields=["deactivated_at", "deactivation_reason", "is_active"])

    def reactivate(self):
        self.is_active = True
        self.deactivated_at = None
        self.deactivation_reason = ""
        self.save(update_fields=["is_active", "deactivated_at", "deactivation_reason"])


class DeviceSession(models.Model):
    """
    [SOLID - Single Responsibility Principle]
    Audita e controla as sessões de login ativas por dispositivo físico (Mesa/Mobile).
    Garante que tokens locais antigos possam ser invalidados remotamente.
    """
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name="sessions")
    device_id = models.CharField("Identificador Único do Aparelho", max_length=64)
    user_agent = models.CharField("Navegador / App", max_length=255, blank=True)
    ip_address = models.GenericIPAddressField("Endereço IP", null=True, blank=True)
    is_active = models.BooleanField("Sessão Válida?", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    terminated_at = models.DateTimeField(null=True, blank=True)
    termination_reason = models.CharField(max_length=32, blank=True)

    class Meta:
        app_label = 'authentication'
        verbose_name = "Auditoria - Sessão de Dispositivo"
        verbose_name_plural = "Auditoria - Sessões de Dispositivos"
        constraints = [
            models.UniqueConstraint(
                fields=['professional', 'device_id'],
                name='uniq_professional_device_session'
            )
        ]
        indexes = [
            models.Index(fields=["professional", "is_active"]),
            models.Index(fields=["professional", "device_id"]),
        ]

    def __str__(self):
        status = "Ativa" if self.is_active else "Encerrada"
        return f"{self.professional.email} — Dispositivo: {self.device_id} ({status})"

    def terminate(self, reason: str = "logout"):
        self.is_active = False
        self.terminated_at = timezone.now()
        self.termination_reason = reason[:32]
        self.save(update_fields=["is_active", "terminated_at", "termination_reason"])


class ProfessionalSettings(models.Model):
    """
    [SOLID - Single Responsibility Principle]
    Armazena as parametrizações de funcionamento de agenda privada de cada profissional.
    """
    class DefaultVisitType(models.TextChoices):
        """[Alinhamento com App Clinic] Sincronizado com enums limpos adotados na Agenda."""
        CONSULTA = "consulta", "Consulta"
        RETORNO = "retorno", "Retorno"
        OUTRO = "outro", "Outro compromisso"

    professional = models.OneToOneField(
        Professional,
        on_delete=models.CASCADE,
        related_name="settings",
        verbose_name="Profissional",
    )
    work_start_hour = models.PositiveSmallIntegerField("Hora de Início da Agenda", default=6)
    work_start_minute = models.PositiveSmallIntegerField(default=0)
    work_end_hour = models.PositiveSmallIntegerField("Hora de Término da Agenda", default=21)
    work_end_minute = models.PositiveSmallIntegerField(default=0)
    slot_minutes = models.PositiveSmallIntegerField("Intervalo de Grade (Minutos)", default=10)
    default_duration_minutes = models.PositiveSmallIntegerField("Duração Sugerida de Atendimento", default=60)
    
    default_visit_type = models.CharField(
        "Tipo Sugerido de Atendimento",
        max_length=20,
        choices=DefaultVisitType.choices,
        default=DefaultVisitType.CONSULTA,
    )

    confirm_message_enabled = models.BooleanField("Disparar confirmações automáticas?", default=False)
    confirm_message_template = models.TextField("Template da Mensagem de Alerta", blank=True)

    # Configurações para automações do Telegram.
    reminder_enabled = models.BooleanField(default=False)
    reminder_minutes_before = models.PositiveSmallIntegerField(
        default=90,
        help_text="Quantos minutos antes do compromisso enviar o lembrete Telegram."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'authentication'
        verbose_name = "Configuração do Profissional"
        verbose_name_plural = "Configurações de Profissionais"

    def __str__(self):
        start = f"{self.work_start_hour:02d}:{self.work_start_minute:02d}"
        end = f"{self.work_end_hour:02d}:{self.work_end_minute:02d}"
        return f"Configurações Clínicas de {self.professional.email} ({start} - {end})"

