import uuid
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from voice_picker.models import UploadedFile, Transcription
from member_management.models import Organization


class Command(BaseCommand):
    help = 'Create test transcription data for UI testing'

    def handle(self, *args, **options):
        # テスト用組織を取得または作成
        organization, created = Organization.objects.get_or_create(
            name='TestCompany',
            defaults={
                'phone_number': '03-1234-5678',
            }
        )

        # テスト用UploadedFileを作成
        uploaded_file = UploadedFile.objects.create(
            id=uuid.uuid4(),
            organization=organization,
            file='test_files/meeting_recording.mp3',  # 仮のファイルパス
            status=UploadedFile.Status.COMPLETED,
            duration=1800.0,  # 30分
            summarization=self.get_sample_summarization(),
            issue=self.get_sample_issues(),
            solution=self.get_sample_solutions(),
            hls_playlist_path='hls/test/master.m3u8',
        )

        # テスト用文字起こしデータを作成
        transcription_data = self.get_sample_transcription_data()

        for segment in transcription_data:
            Transcription.objects.create(
                uploaded_file=uploaded_file,
                start_time=segment['start_time'],
                text=segment['text'],
                speaker=segment.get('speaker'),
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created test data:\n'
                f'- UploadedFile ID: {uploaded_file.id}\n'
                f'- Created {len(transcription_data)} transcription segments\n'
                f'- Organization: {organization.name}'
            )
        )

    def get_sample_summarization(self):
        return '''# 会議要約

## 会議概要
今回の会議では、新プロダクトの開発進捗と今後のロードマップについて議論しました。主要な決定事項と課題が明確になり、次のステップが具体化されました。

## 主要な議題
1. **開発進捗の報告**
   - フロントエンド開発: 80%完了
   - バックエンド開発: 70%完了
   - テスト実装: 50%完了

2. **リリースタイムライン**
   - アルファ版: 来月末
   - ベータ版: 2ヶ月後
   - 本番リリース: 3ヶ月後

3. **予算とリソース**
   - 開発予算: 目標内で推移
   - 人員体制: 追加リソース必要
   - インフラコスト: 見直し要

## 決定事項
- UIデザインの最終確定
- セキュリティテストの外部委託
- マーケティング戦略の策定開始

## 次回アクション
各チームが具体的なタスクを持ち帰り、来週までに詳細スケジュールを作成することが決定されました。'''

    def get_sample_issues(self):
        return '''# 特定された課題

## 緊急度の高い課題

### 1. 開発リソース不足
- **問題**: フロントエンド開発者が1名不足
- **影響**: リリーススケジュールの遅延リスク
- **期限**: 2週間以内に解決必要

### 2. テストカバレッジの低さ
- **問題**: 単体テストカバレッジが40%
- **影響**: 品質リスクの増大
- **期限**: 1ヶ月以内に80%まで向上

## 中程度の課題

### 3. セキュリティ要件の未確定
- **問題**: セキュリティ基準が明確でない
- **影響**: 設計変更の可能性
- **対応**: 外部専門家への相談

### 4. パフォーマンス最適化
- **問題**: 大量データ処理時の応答時間
- **影響**: ユーザーエクスペリエンスの低下
- **対応**: アルゴリズム見直し

## 軽微な課題

### 5. ドキュメントの更新遅れ
- **問題**: API仕様書が古い
- **影響**: 開発効率の低下
- **対応**: 定期的な更新プロセス確立

### 6. 開発環境の統一
- **問題**: チーム間で開発環境が異なる
- **影響**: デバッグ時間の増加
- **対応**: Docker環境の導入'''

    def get_sample_solutions(self):
        return '''# 改善提案・取り組み案

## 重点的な取り組み

### 1. チーム体制の強化
**目標**: 開発リソース不足の解消
- **短期施策**:
  - フリーランス開発者の即座採用
  - 既存メンバーの残業時間調整
- **中期施策**:
  - 正社員開発者の新規採用
  - スキルアップ研修の実施
- **期待効果**: 開発速度30%向上

### 2. 品質管理体制の確立
**目標**: テスト品質の向上
- **具体的施策**:
  - TDD（テスト駆動開発）の導入
  - CI/CDパイプラインの構築
  - コードレビュー基準の策定
- **期待効果**: バグ数50%削減

## プロセス改善

### 3. 開発プロセスの最適化
**目標**: 開発効率の向上
- **Agile開発の強化**:
  - スプリント期間の最適化（2週間）
  - デイリースタンドアップの効率化
  - レトロスペクティブの質向上
- **ツール導入**:
  - プロジェクト管理ツールの統一
  - コミュニケーションツールの活用

### 4. 技術基盤の整備
**目標**: 開発環境の標準化
- **インフラ施策**:
  - Docker環境の全チーム導入
  - 開発用データベースの統一
  - 監視・ログシステムの構築
- **セキュリティ施策**:
  - セキュリティガイドラインの策定
  - 定期的な脆弱性診断
  - アクセス権限管理の強化

## 継続的改善

### 5. 長期的な成長戦略
**目標**: 組織力の向上
- **教育・研修**:
  - 技術勉強会の定期開催
  - 外部カンファレンス参加支援
  - メンタリング制度の確立
- **文化醸成**:
  - イノベーション推進
  - 失敗を恐れない文化作り
  - 成果に対する適切な評価

### 6. 顧客価値の最大化
**目標**: ユーザー満足度向上
- **ユーザビリティ**:
  - UXデザインの専門家招聘
  - ユーザーテストの定期実施
  - フィードバック収集システム構築
- **価値提供**:
  - 機能の優先順位明確化
  - MVPアプローチの徹底
  - 継続的な価値検証'''

    def get_sample_transcription_data(self):
        return [
            {
                'start_time': 0,
                'text': 'おはようございます。それでは定刻になりましたので、プロダクト開発会議を開始いたします。',
                'speaker': '司会者',
            },
            {
                'start_time': 8,
                'text': 'まず最初に、前回の会議のアクションアイテムの進捗確認から始めさせていただきます。田中さん、フロントエンド開発の状況はいかがでしょうか？',
                'speaker': '司会者',
            },
            {
                'start_time': 20,
                'text': 'はい、田中です。フロントエンド開発については、現在80%程度完了しております。ユーザーインターフェースの主要部分は実装済みで、残りはポリッシュとバグフィックスが主になります。',
                'speaker': '田中',
            },
            {
                'start_time': 35,
                'text': 'ただし、一点気になるのが、レスポンシブデザインの対応で想定より時間がかかっています。特にモバイル端末での表示調整に課題があります。',
                'speaker': '田中',
            },
            {
                'start_time': 48,
                'text': 'ありがとうございます。佐藤さん、バックエンドの進捗はいかがですか？',
                'speaker': '司会者',
            },
            {
                'start_time': 55,
                'text': '佐藤です。バックエンド開発は現在70%の完了率です。API設計は完了しており、主要な機能実装も済んでいます。',
                'speaker': '佐藤',
            },
            {
                'start_time': 67,
                'text': 'しかし、パフォーマンス最適化とセキュリティ対応がまだ十分ではありません。特に大量データ処理時の応答時間に改善の余地があります。',
                'speaker': '佐藤',
            },
            {
                'start_time': 80,
                'text': 'なるほど。山田さん、テスト関連の状況を教えてください。',
                'speaker': '司会者',
            },
            {
                'start_time': 87,
                'text': '山田です。テストについては現在50%の進捗です。単体テストは40%のカバレッジを達成していますが、まだ不十分な状況です。',
                'speaker': '山田',
            },
            {
                'start_time': 100,
                'text': '統合テストとE2Eテストの実装も遅れており、品質保証の観点で懸念があります。リソース不足が主な要因です。',
                'speaker': '山田',
            },
            {
                'start_time': 115,
                'text': 'わかりました。現状の課題を整理すると、主に人的リソースとパフォーマンス、品質面での課題があるということですね。',
                'speaker': '司会者',
            },
            {
                'start_time': 128,
                'text': 'リリースタイムラインについて確認したいのですが、当初の予定ではアルファ版を来月末、ベータ版を2ヶ月後、本番リリースを3ヶ月後としていました。',
                'speaker': '司会者',
            },
            {
                'start_time': 145,
                'text': '現在の進捗を考慮すると、スケジュールの調整が必要かもしれません。どうでしょうか？',
                'speaker': '司会者',
            },
            {
                'start_time': 155,
                'text': 'フロントエンドの立場からは、アルファ版のリリースは可能だと思います。ただし、機能を絞り込む必要があるかもしれません。',
                'speaker': '田中',
            },
            {
                'start_time': 168,
                'text': 'バックエンドも基本機能は間に合いますが、パフォーマンス最適化を考えると、品質面でのリスクがあります。',
                'speaker': '佐藤',
            },
            {
                'start_time': 180,
                'text': 'テストカバレッジを80%まで上げるには、少なくとも追加で1ヶ月は必要です。品質を重視するなら、スケジュール調整を検討すべきです。',
                'speaker': '山田',
            },
            {
                'start_time': 195,
                'text': 'ありがとうございます。では、改善案について議論しましょう。まず、リソース不足への対応ですが、短期的な解決策はありますか？',
                'speaker': '司会者',
            },
            {
                'start_time': 208,
                'text': 'フリーランスの開発者を即座に採用することは可能だと思います。特にフロントエンド開発者を1名追加できれば、大きく改善されるでしょう。',
                'speaker': '田中',
            },
            {
                'start_time': 222,
                'text': 'テスト分野でも、外部のQAエンジニアを一時的に活用することで、テストカバレッジの向上を図れます。',
                'speaker': '山田',
            },
            {
                'start_time': 235,
                'text': 'それと並行して、開発プロセスの改善も重要ですね。TDD（テスト駆動開発）の導入やCI/CDパイプラインの構築を進めてはどうでしょうか？',
                'speaker': '佐藤',
            },
            {
                'start_time': 250,
                'text': '良いアイデアですね。長期的には、チーム全体のスキルアップも重要です。定期的な技術勉強会の開催や外部研修への参加も検討しましょう。',
                'speaker': '司会者',
            },
            {
                'start_time': 265,
                'text': 'セキュリティ面については、外部の専門家に相談することをお勧めします。社内だけでは限界があります。',
                'speaker': '佐藤',
            },
            {
                'start_time': 278,
                'text': 'それでは、今日の議論を踏まえて、アクションアイテムを整理しましょう。',
                'speaker': '司会者',
            },
            {
                'start_time': 287,
                'text': 'フリーランス開発者の採用、外部QAエンジニアの活用、セキュリティ専門家への相談、これらを来週までに具体的な計画として作成します。',
                'speaker': '司会者',
            },
            {
                'start_time': 302,
                'text': 'また、各チームには詳細なタスクスケジュールの見直しをお願いします。次回会議は来週の同じ時間で予定しています。',
                'speaker': '司会者',
            },
            {
                'start_time': 315,
                'text': '本日は貴重な意見をありがとうございました。それでは、これで会議を終了いたします。お疲れさまでした。',
                'speaker': '司会者',
            },
        ]