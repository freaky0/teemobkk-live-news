from django import forms
from .places import validate_external_place_url
REGIONS = [("bangkok", "방콕"), ("chiangmai", "치앙마이"), ("phuket", "푸껫"), ("common", "지역 공통")]
CATEGORIES = [("notice", "공지"), ("free", "자유게시판"), ("questions", "질문/답변"), ("market", "중고게시판"), ("jobs", "구인구직"), ("foodtravel", "맛집/여행지"), ("living", "생활 질문"), ("visa", "비자·체류"), ("travel", "교통·여행")]
class PostForm(forms.Form):
    title = forms.CharField(label="제목", min_length=5, max_length=100, widget=forms.TextInput(attrs={"placeholder": "어떤 점이 궁금한가요?", "autocomplete": "off"}))
    region = forms.ChoiceField(label="지역", choices=REGIONS)
    category = forms.ChoiceField(label="주제", choices=CATEGORIES)
    body = forms.CharField(label="상황과 질문", min_length=20, max_length=6000, widget=forms.Textarea(attrs={"rows": 10}))
    privacy = forms.BooleanField(label="개인정보와 타인의 비공개 정보를 넣지 않았습니다.")

    def __init__(self, *args, staff=False, editing=False, **kwargs):
        super().__init__(*args, **kwargs)
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
        self.fields['place_url'] = forms.CharField(label='외부 장소 링크', max_length=500, required=False)
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
class CommentForm(forms.Form):
    body = forms.CharField(label="답변 내용", min_length=5, max_length=3000, widget=forms.Textarea(attrs={"rows": 5}))

class NewsCommentForm(forms.Form):
    body = forms.CharField(label="댓글 내용", min_length=5, max_length=3000, widget=forms.Textarea(attrs={"rows": 4, "id": "id_news_comment_body"}))

class AppealForm(forms.Form):
    details = forms.CharField(label="이의신청 내용", min_length=5, max_length=2000, widget=forms.Textarea(attrs={"rows": 5}))


class ReportForm(forms.Form):
    reason = forms.ChoiceField(label="신고 사유", choices=[("outdated", "오래되거나 잘못된 정보"), ("privacy", "개인정보 노출"), ("spam", "광고·스팸"), ("abuse", "공격·괴롭힘")])
    details = forms.CharField(label="설명", min_length=5, max_length=2000, widget=forms.Textarea(attrs={"rows": 5}))
