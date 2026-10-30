from django import forms
from .models import BoardCategory
from .places import validate_external_place_url
from .post_media import MAX_POST_IMAGES, sanitize_post_image, validate_post_image_url
REGIONS = [("bangkok", "방콕"), ("chiangmai", "치앙마이"), ("phuket", "푸껫"), ("common", "지역 공통")]
CATEGORIES = [("notice", "공지"), ("free", "자유게시판"), ("questions", "질문/답변"), ("market", "중고게시판"), ("jobs", "구인구직"), ("foodtravel", "맛집/여행지"), ("living", "생활 질문"), ("visa", "비자·체류"), ("travel", "교통·여행")]


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        files = data if isinstance(data, (list, tuple)) else [data]
        if len(files) > MAX_POST_IMAGES:
            raise forms.ValidationError("사진은 게시글당 최대 5장까지 올릴 수 있어요.")
        return [forms.FileField.clean(self, upload, initial) for upload in files]


class PostForm(forms.Form):
    title = forms.CharField(label="제목", min_length=5, max_length=100, widget=forms.TextInput(attrs={"placeholder": "제목을 입력해 주세요.", "autocomplete": "off"}))
    region = forms.ChoiceField(label="지역", choices=REGIONS)
    category = forms.ChoiceField(label="게시판", choices=CATEGORIES)
    board_category = forms.ChoiceField(label="세부 분류 (선택)", required=False)
    body = forms.CharField(label="내용", min_length=20, max_length=6000, widget=forms.Textarea(attrs={"rows": 10, "aria-describedby": "id_body_hint"}))
    image_uploads = MultipleFileField(label="사진 파일", required=False, widget=MultipleFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}), help_text="JPG, PNG, WebP · 한 장당 5MB 이하 · 게시글당 최대 5장")
    image_urls = forms.CharField(label="사진 링크", required=False, widget=forms.Textarea(attrs={"rows": 3, "placeholder": "https://example.com/photo.jpg\n사진 링크를 한 줄에 하나씩 입력"}), help_text="공개 이미지 주소를 https://로 시작하는 링크로 입력해 주세요. 한 줄에 하나씩 적을 수 있어요.")
    privacy = forms.BooleanField(label="개인정보나 다른 사람의 비공개 정보를 포함하지 않았습니다.")

    def __init__(self, *args, staff=False, editing=False, existing_images=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.existing_images = list(existing_images)
        self.existing_image_ids = {str(image.pk) for image in self.existing_images}
        categories = list(BoardCategory.objects.all())
        self.fields['board_category'].choices = [('', '선택 안 함')] + [
            (board, [(str(item.pk), item.name) for item in categories if item.board == board])
            for board, _ in BoardCategory._meta.get_field('board').choices
            if any(item.board == board for item in categories)
        ]
        self.fields['market_kind'] = forms.ChoiceField(label='글 종류', choices=[('', '선택'), ('sell', '판매'), ('buy', '구매')], required=False)
        self.fields['market_price'] = forms.DecimalField(label='가격 (THB)', max_digits=12, decimal_places=2, min_value=0, required=False)
        self.fields['market_region'] = forms.ChoiceField(label='거래 지역', choices=[('', '선택'), *REGIONS], required=False)
        self.fields['market_status'] = forms.ChoiceField(label='거래 상태', choices=[('', '선택'), ('active', '거래 중'), ('reserved', '예약'), ('completed', '완료')], required=False)
        self.fields['job_kind'] = forms.ChoiceField(label='구인/구직 종류', choices=[('', '선택'), ('hiring', '구인'), ('seeking', '구직')], required=False)
        self.fields['job_region'] = forms.ChoiceField(label='근무 지역', choices=[('', '선택'), *REGIONS], required=False)
        self.fields['job_compensation'] = forms.CharField(label='보상 정보', max_length=200, required=False)
        self.fields['job_status'] = forms.ChoiceField(label='모집 상태', choices=[('', '선택'), ('open', '모집 중'), ('closed', '마감')], required=False)
        self.fields['place_name'] = forms.CharField(label='장소명', max_length=160, required=False)
        self.fields['place_region'] = forms.ChoiceField(label='장소 지역', choices=[('', '선택'), *REGIONS], required=False)
        self.fields['place_note'] = forms.CharField(label='방문 메모', max_length=500, required=False, widget=forms.Textarea(attrs={'rows': 3}))
        self.fields['place_url'] = forms.CharField(label='Google 지도 또는 장소 링크', max_length=2048, required=False, widget=forms.URLInput(attrs={'placeholder': 'https://maps.app.goo.gl/...'}), help_text='Google 지도 공유 링크를 붙여 넣으면 게시글에 지도 미리보기가 표시됩니다.')
        if staff:
            self.fields['is_pinned'] = forms.BooleanField(label='공지 상단 고정 (공지 글만 가능)', required=False)
        if editing:
            self.fields['confirm_board_data_removal'] = forms.BooleanField(label='게시판 변경 시 기존 게시판 정보를 삭제하는 데 동의합니다.', required=False)
            self.fields['board_data_version'] = forms.CharField(required=False, widget=forms.HiddenInput)
    def _clean_fields(self):
        category = self.data.get('category')
        for name, bound_field in self._bound_items():
            if any(name.startswith(prefix) and category != board for prefix, board in (('market_', 'market'), ('job_', 'jobs'), ('place_', 'foodtravel'))):
                continue
            try:
                self.cleaned_data[name] = bound_field.field._clean_bound_field(bound_field)
                if hasattr(self, 'clean_' + name):
                    self.cleaned_data[name] = getattr(self, 'clean_' + name)()
            except forms.ValidationError as exc:
                self.add_error(name, exc)

    def clean_place_url(self):
        return validate_external_place_url(self.cleaned_data['place_url'])

    def clean_image_uploads(self):
        uploads = self.cleaned_data.get('image_uploads') or []
        try:
            return [sanitize_post_image(upload) for upload in uploads]
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc

    def clean_image_urls(self):
        raw = self.cleaned_data.get('image_urls') or ''
        values = [line.strip() for line in raw.splitlines() if line.strip()]
        try:
            return [validate_post_image_url(value) for value in values]
        except forms.ValidationError as exc:
            raise forms.ValidationError(exc.messages) from exc

    def clean(self):
        cleaned = super().clean()
        remove_ids = self.data.getlist('remove_image_ids') if hasattr(self.data, 'getlist') else []
        remove_ids = list(dict.fromkeys(remove_ids))
        if not set(remove_ids).issubset(self.existing_image_ids):
            self.add_error(None, "삭제할 사진을 다시 확인해 주세요.")
            remove_ids = []
        cleaned['remove_image_ids'] = remove_ids
        remaining = len(self.existing_images) - len(remove_ids)
        additions = len(cleaned.get('image_uploads') or []) + len(cleaned.get('image_urls') or [])
        if remaining + additions > MAX_POST_IMAGES:
            self.add_error('image_urls', f"기존 사진을 포함해 게시글당 최대 {MAX_POST_IMAGES}장까지 등록할 수 있어요.")
        return cleaned

    def clean_board_category(self):
        return self.cleaned_data['board_category'] or None
class CommentForm(forms.Form):
    body = forms.CharField(label="답변 내용", min_length=5, max_length=3000, widget=forms.Textarea(attrs={"rows": 5}))

class NewsCommentForm(forms.Form):
    body = forms.CharField(label="댓글 내용", min_length=5, max_length=3000, widget=forms.Textarea(attrs={"rows": 4, "id": "id_news_comment_body"}))

class AppealForm(forms.Form):
    details = forms.CharField(label="이의신청 내용", min_length=5, max_length=2000, widget=forms.Textarea(attrs={"rows": 5}))


class ReportForm(forms.Form):
    reason = forms.ChoiceField(label="신고 사유", choices=[("outdated", "오래되거나 잘못된 정보"), ("privacy", "개인정보 노출"), ("spam", "광고·스팸"), ("abuse", "공격·괴롭힘")])
    details = forms.CharField(label="설명", min_length=5, max_length=2000, widget=forms.Textarea(attrs={"rows": 5}))
