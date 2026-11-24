from rest_framework import serializers

from .mentor_models import MentorOffer, MentorProfile, MentorSession, SessionRating, SessionRequest, Wallet, WalletTransaction


class MentorProfileSerializer(serializers.ModelSerializer):
    mentor_name = serializers.CharField(source='user.full_name', read_only=True)
    mentor_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = MentorProfile
        fields = ('id', 'user', 'mentor_name', 'mentor_email', 'qualifications', 'topics', 'hourly_rate', 'is_available', 'created_at', 'updated_at')
        read_only_fields = ('id', 'user', 'mentor_name', 'mentor_email', 'created_at', 'updated_at')


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ('id', 'balance', 'created_at', 'updated_at')
        read_only_fields = fields


class WalletTransactionSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source='get_kind_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = WalletTransaction
        fields = ('id', 'kind', 'kind_label', 'status', 'status_label', 'amount', 'fee_amount', 'deduction_amount', 'credited_amount', 'session', 'note', 'created_at')
        read_only_fields = fields


class SessionRequestSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    offers = serializers.SerializerMethodField()

    class Meta:
        model = SessionRequest
        fields = ('id', 'student', 'student_name', 'topic', 'problem', 'tried', 'preferred_duration_hours', 'preferred_times', 'status', 'offers', 'created_at', 'updated_at')
        read_only_fields = ('id', 'student', 'student_name', 'status', 'offers', 'created_at', 'updated_at')

    def get_offers(self, obj):
        return MentorOfferSerializer(obj.offers.all(), many=True).data


class MentorOfferSerializer(serializers.ModelSerializer):
    mentor_name = serializers.CharField(source='mentor.full_name', read_only=True)

    class Meta:
        model = MentorOffer
        fields = ('id', 'session_request', 'mentor', 'mentor_name', 'mentor_profile', 'hourly_rate', 'proposed_time', 'message', 'status', 'created_at')
        read_only_fields = ('id', 'mentor', 'mentor_name', 'mentor_profile', 'status', 'created_at')
        extra_kwargs = {'hourly_rate': {'required': False}}


class SessionRatingSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    mentor_name = serializers.CharField(source='mentor.full_name', read_only=True)

    class Meta:
        model = SessionRating
        fields = ('id', 'session', 'student', 'student_name', 'mentor', 'mentor_name', 'rating', 'comment', 'created_at')
        read_only_fields = ('id', 'student', 'student_name', 'mentor', 'mentor_name', 'created_at')
        extra_kwargs = {'comment': {'max_length': 5000}}


class MentorSessionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    mentor_name = serializers.CharField(source='mentor.full_name', read_only=True)
    rating = serializers.SerializerMethodField()

    class Meta:
        model = MentorSession
        fields = ('id', 'student', 'student_name', 'mentor', 'mentor_name', 'mentor_profile', 'source', 'session_request', 'offer', 'topic', 'duration_hours', 'hourly_rate', 'total_fee', 'scheduled_at', 'meet_link', 'status', 'payment_status', 'paid_at', 'rating', 'created_at', 'updated_at')
        read_only_fields = ('id', 'student', 'student_name', 'mentor_name', 'mentor_profile', 'source', 'session_request', 'offer', 'hourly_rate', 'total_fee', 'status', 'payment_status', 'paid_at', 'rating', 'created_at', 'updated_at')

    def get_rating(self, obj):
        rating = getattr(obj, 'rating', None)
        if rating is None:
            return None
        return SessionRatingSerializer(rating).data
