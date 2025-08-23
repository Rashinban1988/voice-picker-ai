from django.db import models
import uuid
from django.utils.translation import gettext_lazy as _
from member_management.models import Organization
from .uploaded_file import UploadedFile


class PromptHistory(models.Model):
    """再生成時に使用されたプロンプトの履歴を記録するモデル"""

    class PromptType(models.TextChoices):
        SUMMARY = 'summary', _('要約')
        ISSUES = 'issues', _('課題')
        SOLUTIONS = 'solutions', _('取り組み案')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='prompt_histories',
        verbose_name='組織'
    )
    uploaded_file = models.ForeignKey(
        UploadedFile,
        on_delete=models.CASCADE,
        related_name='prompt_histories',
        verbose_name='対象ファイル'
    )
    prompt_type = models.CharField(
        max_length=20,
        choices=PromptType.choices,
        verbose_name='プロンプト種別'
    )
    custom_instruction = models.TextField(
        null=True,
        blank=True,
        verbose_name='カスタム指示'
    )
    generated_result = models.TextField(
        null=True,
        blank=True,
        verbose_name='生成結果'
    )
    # 週次分析用のメタデータ
    week_of_year = models.IntegerField(verbose_name='年の何週目')
    year = models.IntegerField(verbose_name='年')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')

    # プロンプト分析用フィールド
    instruction_keywords = models.JSONField(
        default=list,
        blank=True,
        verbose_name='指示キーワード',
        help_text='分析用のキーワードリスト'
    )
    instruction_category = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='指示カテゴリ',
        help_text='技術的、ビジネス、改善案など'
    )

    class Meta:
        verbose_name = 'プロンプト履歴'
        verbose_name_plural = 'プロンプト履歴'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'week_of_year', 'year']),
            models.Index(fields=['prompt_type', 'created_at']),
            models.Index(fields=['instruction_category']),
        ]

    def __str__(self):
        return f'{self.organization.name} - {self.get_prompt_type_display()} - {self.created_at.strftime("%Y/%m/%d %H:%M")}'

    @classmethod
    def get_weekly_analysis_data(cls, organization, year, week):
        """指定された週のプロンプト履歴データを取得"""
        return cls.objects.filter(
            organization=organization,
            year=year,
            week_of_year=week
        ).select_related('uploaded_file')

    def save(self, *args, **kwargs):
        if not self.week_of_year or not self.year:
            from datetime import datetime
            dt = self.created_at if self.created_at else datetime.now()
            self.year = dt.year
            self.week_of_year = dt.isocalendar()[1]

        # カスタム指示がある場合、キーワードとカテゴリを自動抽出
        if self.custom_instruction and not self.instruction_keywords:
            self._extract_keywords_and_category()

        super().save(*args, **kwargs)

    def _extract_keywords_and_category(self):
        """カスタム指示からキーワードとカテゴリを自動抽出"""
        instruction_lower = self.custom_instruction.lower()

        # キーワード抽出（簡易版）
        technical_keywords = ['技術', 'テクニカル', 'システム', 'アーキテクチャ', 'コード', 'api', 'データベース']
        business_keywords = ['ビジネス', '売上', '収益', '戦略', 'roi', 'kpi', '顧客', 'マーケティング']
        improvement_keywords = ['改善', '最適化', '効率', '向上', '強化', 'アップグレード', '修正']
        analysis_keywords = ['分析', '解析', '調査', '検討', '評価', '診断']

        keywords = []
        categories = []

        for keyword in technical_keywords:
            if keyword in instruction_lower:
                keywords.append(keyword)
                if '技術' not in categories:
                    categories.append('技術')

        for keyword in business_keywords:
            if keyword in instruction_lower:
                keywords.append(keyword)
                if 'ビジネス' not in categories:
                    categories.append('ビジネス')

        for keyword in improvement_keywords:
            if keyword in instruction_lower:
                keywords.append(keyword)
                if '改善' not in categories:
                    categories.append('改善')

        for keyword in analysis_keywords:
            if keyword in instruction_lower:
                keywords.append(keyword)
                if '分析' not in categories:
                    categories.append('分析')

        self.instruction_keywords = list(set(keywords))
        self.instruction_category = ', '.join(categories) if categories else 'その他'