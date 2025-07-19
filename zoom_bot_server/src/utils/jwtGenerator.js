const jwt = require('jsonwebtoken');
const crypto = require('crypto');

class JWTGenerator {
    constructor() {
        this.sdkKey = process.env.ZOOM_MEETING_SDK_KEY;
        this.sdkSecret = process.env.ZOOM_MEETING_SDK_SECRET;
    }

    /**
     * Generate JWT token for Zoom Meeting SDK
     * @param {string} meetingNumber - The meeting number
     * @param {number} role - User role (0 for participant, 1 for host)
     * @param {number} userIdentity - Optional user identity
     * @returns {string} JWT token
     */
    generateSDKJWT(meetingNumber, role = 0, userIdentity = null) {
        if (!this.sdkKey || !this.sdkSecret) {
            throw new Error('Zoom SDK credentials not configured');
        }

        const now = Math.floor(Date.now() / 1000);
        const exp = now + (2 * 60 * 60); // 2 hours from now
        const tokenExp = now + (2 * 60 * 60); // Token expiration

        const payload = {
            iss: this.sdkKey,
            appKey: this.sdkKey,
            iat: now,
            exp: exp,
            tokenExp: tokenExp,
            alg: 'HS256'
        };

        // Add meeting-specific claims
        if (meetingNumber) {
            payload.mn = meetingNumber;
            payload.role = role;
        }

        // Add user identity if provided
        if (userIdentity) {
            payload.identity = userIdentity;
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
            payload,
            tokenLength: token.length
        });

        return token;
    }

    /**
     * Generate signature for Zoom SDK authentication
     * @param {string} meetingNumber - The meeting number
     * @param {number} role - User role
     * @returns {object} Signature object
     */
    generateSignature(meetingNumber, role = 0) {
        const timestamp = Date.now();
        const msg = Buffer.from(this.sdkKey + meetingNumber + timestamp + role).toString('base64');
        const hash = crypto.createHmac('sha256', this.sdkSecret).update(msg).digest('base64');
        
        return {
            signature: hash,
            timestamp: timestamp,
            appKey: this.sdkKey,
            meetingNumber: meetingNumber,
            role: role
        };
    }

    /**
     * Validate JWT token
     * @param {string} token - JWT token to validate
     * @returns {object} Decoded payload if valid
     */
    validateJWT(token) {
        try {
            return jwt.verify(token, this.sdkSecret, { algorithms: ['HS256'] });
        } catch (error) {
            throw new Error(`JWT validation failed: ${error.message}`);
        }
    }

    /**
     * Generate comprehensive authentication object for C++ bot
     * @param {string} meetingNumber - Meeting number
     * @param {string} password - Meeting password (optional)
     * @param {string} userName - User display name
     * @returns {object} Authentication configuration
     */
    generateBotAuthConfig(meetingNumber, password = '', userName = 'Recording Bot') {
        const jwtToken = this.generateSDKJWT(meetingNumber, 0);
        const signature = this.generateSignature(meetingNumber, 0);
        
        return {
            jwt: jwtToken,
            signature: signature,
            meetingNumber: meetingNumber,
            password: password,
            userName: userName,
            sdkKey: this.sdkKey,
            timestamp: Date.now()
        };
    }
}

module.exports = JWTGenerator;