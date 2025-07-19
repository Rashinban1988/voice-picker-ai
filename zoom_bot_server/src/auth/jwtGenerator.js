const jwt = require('jsonwebtoken');

class ZoomJWTGenerator {
    constructor(sdkKey, sdkSecret) {
        this.sdkKey = sdkKey;
        this.sdkSecret = sdkSecret;
    }

    generateJWT(meetingNumber, role = 0) {
        // 現在時刻から30秒前を開始時刻とする（クロックスキュー対応）
        const iat = Math.round(new Date().getTime() / 1000) - 30;
        const exp = iat + 60 * 60 * 2; // 2時間後
        const tokenExp = iat + 60 * 60 * 2; // 2時間後（最小1800秒以上）

        const payload = {
            iss: this.sdkKey,
            appKey: this.sdkKey,
            iat: iat,
            exp: exp,
            tokenExp: tokenExp,
            alg: 'HS256'
        };

        // meetingNumberとroleが指定されている場合のみ追加
        if (meetingNumber) {
            payload.mn = meetingNumber;
        }
        if (role !== undefined) {
            payload.role = role;
        }

        const token = jwt.sign(payload, this.sdkSecret, {
            algorithm: 'HS256',
            header: {
                alg: 'HS256',
                typ: 'JWT'
            }
        });
        
        console.log('Generated JWT:', {
            meetingNumber,
            role,
            payload: { ...payload, iat: new Date(iat * 1000), exp: new Date(exp * 1000) },
            tokenLength: token.length
        });

        return token;
    }

    validateJWT(token) {
        try {
            const decoded = jwt.verify(token, this.sdkSecret);
            return { valid: true, decoded };
        } catch (error) {
            return { valid: false, error: error.message };
        }
    }
}

module.exports = ZoomJWTGenerator;