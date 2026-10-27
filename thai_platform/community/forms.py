from django import forms
REGIONS = [("bangkok", "방콕"), ("chiangmai", "치앙마이"), ("phuket", "푸껫"), ("common", "지역 공통")]
CATEGORIES = [("notice", "공지"), ("living", "생활 질문"), ("housing", "주거"), ("visa", "비자·체류"), ("travel", "교통·여행"), ("banking", "은행·생활")]
class PostForm(forms.Form):
    title = forms.CharField(label="제목", min_length=5, max_length=100, widget=forms.TextInput(attrs={"placeholder": "어떤 점이 궁금한가요?", "autocomplete": "off"}))
    region = forms.ChoiceField(label="지역", choices=REGIONS)
    category = forms.ChoiceField(label="주제", choices=CATEGORIES)
    body = forms.CharField(label="상황과 질문", min_length=20, max_length=6000, widget=forms.Textarea(attrs={"rows": 10}))
    privacy = forms.BooleanField(label="개인정보와 타인의 비공개 정보를 넣지 않았습니다.")
class CommentForm(forms.Form):
    body = forms.CharField(label="답변 내용", min_length=5, max_length=3000, widget=forms.Textarea(attrs={"rows": 5}))

class NewsCommentForm(forms.Form):
    body = forms.CharField(label="댓글 내용", min_length=5, max_length=3000, widget=forms.Textarea(attrs={"rows": 4, "id": "id_news_comment_body"}))

class AppealForm(forms.Form):
    details = forms.CharField(label="이의신청 내용", min_length=5, max_length=2000, widget=forms.Textarea(attrs={"rows": 5}))


class ReportForm(forms.Form):
    reason = forms.ChoiceField(label="신고 사유", choices=[("outdated", "오래되거나 잘못된 정보"), ("privacy", "개인정보 노출"), ("spam", "광고·스팸"), ("abuse", "공격·괴롭힘")])
    details = forms.CharField(label="설명", min_length=5, max_length=2000, widget=forms.Textarea(attrs={"rows": 5}))
