# backend/apps/register/models.py
from phonenumber_field.modelfields import PhoneNumberField
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone

class ProfessionalManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("O e-mail é obrigatório")

        email = self.normalize_email(email)
        extra_fields.setdefault("is_staff", False)       # Não é staff
        extra_fields.setdefault("is_superuser", False)   # Nem superusuário

        user = self.model(email=email, **extra_fields)

        if password:
            user.set_password(password)  # Criptografa a senha
        else:
            user.set_unusable_password() # Se for login via código/OTP

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        # Apenas para uso interno, por exemplo: Django Admin
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class Professional(AbstractBaseUser, PermissionsMixin):
    first_name = models.CharField("Nome", max_length=50)
    last_name = models.CharField("Sobrenome", max_length=70)
    display_name = models.CharField(
        "Nome de exibição",
        max_length=100,
        blank=True,
        help_text="Como os clientes a conhecem: ex. 'Podóloga Regiane', 'Dra. Juliana' ou 'Clínica Árcaro'. Se vazio, usa o primeiro nome.",
    )
    phone = PhoneNumberField("Telefone", region="BR", blank=True) # type: ignore
    email = models.EmailField("E-mail", unique=True)

    register_number = models.CharField(
        "Registro Profissional", 
        max_length=30, 
        unique=True,
        blank=True,
        null=True
    )
    specialty = models.CharField("Especialidade", max_length=100, blank=True)
    can_manage_professionals = models.BooleanField(
    default=False,
    verbose_name="Pode gerenciar profissionais"
)
    totp_secret = models.CharField(
        "TOTP Secret",
        max_length=64,
        blank=True,
        help_text="Base32 secret for TOTP (Google Authenticator). Empty = TOTP not configured.",
    )

    # Preferência de tema da interface
    UI_THEME_CHOICES = (
        ("blue", "Azul"),
        ("green", "Verde"),
        ("pink", "Rosa"),
        ("black", "Escuro"),
    )
    ui_theme = models.CharField(
        "Tema da interface",
        max_length=10,
        choices=UI_THEME_CHOICES,
        default="blue",
    )

    # Endereço
    city = models.CharField("Cidade", max_length=50, blank=True)
    state = models.CharField("Estado", max_length=2, blank=True)

    is_staff = models.BooleanField(default=True)
    is_active = models.BooleanField("Ativo", default=True)
    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    deactivated_at = models.DateTimeField("Desativado em", null=True, blank=True)
    deactivation_reason = models.CharField(
        "Motivo desativação", max_length=120, blank=True
    )

    objects = ProfessionalManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} — {self.register_number}"

    # Soft delete helper
    def deactivate(self, reason: str = ""):
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
    """Sessão de dispositivo por profissional para auditoria e controle de limite.

    - device_id: um identificador persistente gerado no frontend (UUID/string curta).
    - is_active: ativa enquanto a sessão estiver em uso; ao sair, marcar inativa e registrar terminated_at.
    - last_seen_at: atualizado quando o dispositivo interage (pode ser via heartbeat/requests autenticadas).
    """

    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name="sessions")
    device_id = models.CharField(max_length=64)
    user_agent = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    terminated_at = models.DateTimeField(null=True, blank=True)
    termination_reason = models.CharField(max_length=32, blank=True)

    class Meta:
        unique_together = ("professional", "device_id")
        indexes = [
            models.Index(fields=["professional", "is_active"]),
            models.Index(fields=["professional", "device_id"]),
        ]

    def __str__(self):
        status = "ativa" if self.is_active else "inativa"
        return f"{self.professional.email} — {self.device_id} ({status})"

    def terminate(self, reason: str = "logout"):
        self.is_active = False
        self.terminated_at = timezone.now()
        self.termination_reason = reason[:32]
        self.save(update_fields=["is_active", "terminated_at", "termination_reason"])


class ProfessionalSettings(models.Model):
    """Configurações por profissional para a agenda e comunicação.

    - work_start_hour/work_start_minute: início padrão da agenda
    - work_end_hour/work_end_minute: fim padrão da agenda
    - slot_minutes: duração dos slots (ex.: 15, 30, 60)
    - default_duration_minutes: duração sugerida para novos compromissos
    - default_visit_type: tipo sugerido para novos compromissos
    - confirm_message_enabled: ativa envio de confirmação (futuro)
    - confirm_message_template: template opcional da mensagem
    """

    DEFAULT_VISIT_TYPE_CHOICES = (
        ("consulta", "Consulta"),
        ("avaliacao", "Avaliação"),
        ("retorno", "Retorno"),
        ("procedimento", "Procedimento"),
        ("outro", "Outro"),
    )

    professional = models.OneToOneField(
        Professional,
        on_delete=models.CASCADE,
        related_name="settings",
        verbose_name="Profissional",
    )
    work_start_hour = models.PositiveSmallIntegerField(default=6)
    work_start_minute = models.PositiveSmallIntegerField(default=0)
    work_end_hour = models.PositiveSmallIntegerField(default=21)
    work_end_minute = models.PositiveSmallIntegerField(default=0)
    slot_minutes = models.PositiveSmallIntegerField(default=10)
    default_duration_minutes = models.PositiveSmallIntegerField(default=60)
    default_visit_type = models.CharField(
        max_length=20,
        choices=DEFAULT_VISIT_TYPE_CHOICES,
        default="consulta",
    )

    confirm_message_enabled = models.BooleanField(default=False)
    confirm_message_template = models.TextField(blank=True)

    # PIX defaults (for quick budget payments)
    PIX_KEY_TYPES = (
        ("telefone", "Telefone"),
        ("cpf", "CPF"),
        ("email", "E-mail"),
        ("aleatoria", "Aleatória"),
    )
    pix_key_type = models.CharField(
        max_length=16, choices=PIX_KEY_TYPES, blank=True, default=""
    )
    pix_key_value = models.CharField(max_length=128, blank=True, default="")

    # Professional reminder settings (Telegram)
    reminder_enabled = models.BooleanField(default=False)
    reminder_minutes_before = models.PositiveSmallIntegerField(
        default=90,
        help_text="Quantos minutos antes do compromisso enviar o lembrete Telegram.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração do Profissional"
        verbose_name_plural = "Configurações de Profissionais"

    def __str__(self):
        start = f"{self.work_start_hour:02d}:{self.work_start_minute:02d}"
        end = f"{self.work_end_hour:02d}:{self.work_end_minute:02d}"
        return (
            f"Config {self.professional.email} "
            f"({start}-{end}/{self.slot_minutes}m/{self.default_duration_minutes}m)"
        )


class WebAuthnCredential(models.Model):
    """Credencial WebAuthn (passkey / biometria) de um profissional.

    Armazena o resultado de um registro bem-sucedido feito via
    navigator.credentials.create() no frontend.  Cada profissional pode ter
    múltiplas credenciais (iPhone, iPad, etc.).
    """

    professional = models.ForeignKey(
        Professional,
        on_delete=models.CASCADE,
        related_name="webauthn_credentials",
    )
    # id base64url retornado pelo @simplewebauthn/browser
    credential_id = models.TextField(unique=True)
    # Chave pública COSE codificada em base64 (bytes brutos do py_webauthn)
    public_key = models.TextField()
    sign_count = models.PositiveIntegerField(default=0)
    # Nome amigável (user-agent resumido, e.g. "iPhone de Eduardo")
    device_name = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Credencial WebAuthn"
        verbose_name_plural = "Credenciais WebAuthn"

    def __str__(self):
        return f"{self.professional.email} — {self.device_name or self.credential_id[:12]}"

