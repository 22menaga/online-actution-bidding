from rest_framework import serializers
from .models import User,SellerProfile,BuyerProfile,SellerVerification
class UserSerializer(serializers.ModelSerializer):
 class Meta: model=User; fields=['id','username','email','role','email_verified','is_suspended','created_at']; read_only_fields=['id','role','email_verified','is_suspended','created_at']
class RegisterSerializer(serializers.ModelSerializer):
 password=serializers.CharField(write_only=True,min_length=10)
 class Meta: model=User; fields=['username','email','password','role']
 def validate_role(self,value):
  if value=='ADMIN': raise serializers.ValidationError('Admin accounts are provisioned by trusted operators.')
  return value
 def create(self,v):
  role=v.pop('role',User.Roles.BUYER); u=User.objects.create_user(**v,role=role); (SellerProfile.objects.create(user=u) if role=='SELLER' else BuyerProfile.objects.create(user=u)); return u
class SellerVerificationSerializer(serializers.ModelSerializer):
 seller_name=serializers.CharField(source='seller.user.username',read_only=True); seller_email=serializers.CharField(source='seller.user.email',read_only=True)
 class Meta: model=SellerVerification; fields=['id','seller_name','seller_email','legal_name','document_type','document_reference','status','notes','created_at','reviewed_at']; read_only_fields=['status','notes','reviewed_at']
