class OrganizationForm:
    def __init__(self, org_id, name, phone_number):
        self.org_id = org_id
        self.name = name
        self.phone_number = phone_number

    def is_valid(self):
        # バリデーションロジックをここに追加
        return True

class MemberForm:
    def __init__(self, member_id, email, phone_number):
        self.member_id = member_id
        self.email = email
        self.phone_number = phone_number

    def is_valid(self):
        # バリデーションロジックをここに追加
        return True