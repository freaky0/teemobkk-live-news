import unicodedata
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from allauth.account.forms import LoginForm
from .models import MemberProfile

class MemberPasswordLoginForm(LoginForm):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['password']=forms.CharField(
            label='비밀번호',
            strip=False,
            widget=forms.PasswordInput(attrs={'autocomplete':'current-password'}),
        )
    def clean(self):
        cleaned_data=super().clean()
        if self._errors or not getattr(self,'user',None):
            return cleaned_data
        allowed=MemberProfile.objects.filter(
            user=self.user,
            email_login_enabled=True,
            email_verified_at__isnull=False,
        ).exists()
        if not allowed:
            raise ValidationError('이메일 또는 비밀번호를 확인해 주세요.')
        return cleaned_data

class AccountClosureForm(forms.Form):
    confirm = forms.BooleanField(label="계정 비활성화와 질문·답변 보존을 확인했습니다.")


class EmailRequestForm(forms.Form):
    email = forms.EmailField(label="이메일 주소", max_length=254, widget=forms.EmailInput(attrs={"autocomplete":"email", "placeholder":"name@example.com"}))
    def clean_email(self):
        return self.cleaned_data["email"].strip().casefold()

class OnboardingForm(forms.Form):
    nickname = forms.RegexField(regex=r"^[가-힣A-Za-z0-9_]{2,20}$", label="닉네임", min_length=2, max_length=20, help_text="한글·영문·숫자·밑줄로 2~20자", error_messages={"invalid":"한글·영문·숫자·밑줄로 2~20자를 입력하세요."})
    terms = forms.BooleanField(label="이용약관을 확인하고 동의합니다.")
    privacy = forms.BooleanField(label="개인정보 수집·이용 안내를 확인하고 동의합니다.")
    def __init__(self,*args,user,**kwargs):
        self.user=user
        super().__init__(*args,**kwargs)
    def clean_nickname(self):
        nickname=unicodedata.normalize("NFKC",self.cleaned_data["nickname"])
        key=nickname.casefold()
        if MemberProfile.objects.filter(nickname_key=key).exclude(user=self.user).exists() or get_user_model().objects.filter(username__iexact=nickname).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("다른 닉네임을 입력해 주세요.")
        return nickname
