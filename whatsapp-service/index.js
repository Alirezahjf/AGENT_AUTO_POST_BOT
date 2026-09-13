const crypto = require('crypto')
global.crypto = crypto

const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys')
const express = require('express')
const qrcodeTerminal = require('qrcode-terminal')
const QRCode = require('qrcode')
const pino = require('pino')
const fs = require('fs')
const path = require('path')

const app = express()
app.use(express.json({limit: '50mb'}))
const PORT = 3001
const logger = pino({ level: 'silent' })
const sessions = {}

async function restoreSessionsFromDisk() {
    try {
        const authDir = path.join('auth')
        if (!fs.existsSync(authDir)) {
            console.log('📁 No auth dir, skipping restore')
            return
        }
        const userDirs = fs.readdirSync(authDir)
        console.log(`🔄 Found ${userDirs.length} auth folders to restore: ${userDirs.join(', ')}`)
        for (const userId of userDirs) {
            const userAuthPath = path.join(authDir, userId)
            if (fs.statSync(userAuthPath).isDirectory()) {
                try {
                    // Check if has creds file
                    const files = fs.readdirSync(userAuthPath)
                    if (files.length > 0) {
                        console.log(`♻️ Restoring session for ${userId} (${files.length} files)`)
                        await createSession(userId)
                        // Wait a bit for connection
                        await new Promise(r => setTimeout(r, 2000))
                    }
                } catch (e) {
                    console.error(`❌ Failed to restore ${userId}: ${e.message}`)
                }
            }
        }
        console.log(`✅ Restore check done, ${Object.keys(sessions).length} sessions in memory`)
    } catch (e) {
        console.error(`❌ restoreSessionsFromDisk error: ${e}`)
    }
}

async function createSession(userId, phoneNumber = null) {
    const userIdStr = String(userId)
    console.log(`🔧 Creating session for ${userIdStr} phone=${phoneNumber}`)
    if (sessions[userIdStr] && sessions[userIdStr].isConnected) return sessions[userIdStr]
    if (sessions[userIdStr] && sessions[userIdStr].sock) { try { sessions[userIdStr].sock.end() } catch(e) {} }
    const authFolder = path.join('auth', userIdStr)
    if (!fs.existsSync(authFolder)) fs.mkdirSync(authFolder, { recursive: true })
    const { state, saveCreds } = await useMultiFileAuthState(authFolder)
    const { version } = await fetchLatestBaileysVersion()
    console.log(`📦 Baileys version ${version} for ${userIdStr}`)
    const sock = makeWASocket({ version, auth: state, logger, printQRInTerminal: false, browser: ['AGENT_AUTO_POST_BOT', 'Chrome', '1.0.0'] })
    const session = { sock, isConnected: false, qr: null, qrImage: null, pairingCode: null, phoneNumber, lastUpdate: new Date(), userId: userIdStr, lastQR: null }
    sessions[userIdStr] = session
    sock.ev.on('creds.update', saveCreds)
    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update
        session.lastUpdate = new Date()
        if (qr) {
            session.qr = qr
            session.lastQR = qr
            console.log(`📱 QR for ${userIdStr} - SCAN NOW!`)
            qrcodeTerminal.generate(qr, { small: true })
            try { 
                session.qrImage = await QRCode.toDataURL(qr, { width: 400, margin: 2 })
                console.log(`🖼️ QR image ready for ${userIdStr}`)
            } catch(e) { console.error(`QR image error: ${e}`) }
        }
        if (connection === 'close') {
            const statusCode = lastDisconnect?.error?.output?.statusCode
            const reason = lastDisconnect?.error?.message || 'unknown'
            console.log(`❌ Closed for ${userIdStr} code=${statusCode} reason=${reason}`)
            session.isConnected = false
            if (statusCode === DisconnectReason.loggedOut) {
                console.log(`🚫 Logged out ${userIdStr}`)
                try { fs.rmSync(authFolder, { recursive: true, force: true }) } catch(e) {}
                delete sessions[userIdStr]
            } else {
                console.log(`🔄 Reconnect ${userIdStr} in 5s...`)
                setTimeout(() => createSession(userIdStr, phoneNumber), 5000)
            }
        } else if (connection === 'open') {
            console.log(`✅✅✅ CONNECTED for ${userIdStr}! ✅✅✅`)
            session.isConnected = true
            session.qr = null
            session.qrImage = null
            session.pairingCode = null
            
            // ارسال پیام تست خودکار برای اطمینان از اتصال
            try {
                // یک پیام تست به خود کاربر یا به شماره تست
                // برای اطمینان از اینکه ارسال کار می‌کند
                console.log(`📤 Sending test message for ${userIdStr} to verify connection...`)
                // پیام تست را به خود اکانت واتساپ می‌فرستیم (یا اگر phoneNumber دارد به آن)
                // برای گروه‌ها، بعدا کاربر مقصد را انتخاب می‌کند
                // فعلا فقط لاگ می‌کنیم که متصل شد
                setTimeout(async () => {
                    try {
                        // اگر phoneNumber دارد و شخصی است، یک پیام تست بفرست
                        if (session.phoneNumber && !session.phoneNumber.includes('@g.us')) {
                            let testTo = session.phoneNumber
                            if (/^\d+$/.test(testTo)) {
                                testTo = `${testTo}@s.whatsapp.net`
                            }
                            await session.sock.sendMessage(testTo, { text: '✅ واتساپ متصل شد! اوکی وصله 🎉\n\nربات آماده ارسال پست است' })
                            console.log(`✅ Test message sent to ${testTo} for ${userIdStr}`)
                        }
                    } catch (e) {
                        console.log(`⚠️ Test message failed for ${userIdStr}: ${e.message} (normal if destination not set)`)
                    }
                }, 3000)
            } catch (e) {
                console.log(`⚠️ Test message setup failed: ${e.message}`)
            }
        }
    })
    return session
}

async function getPairingCodeWithRetry(sock, phoneNumber, retries = 2) {
    if (!phoneNumber) return null
    let cleanPhone = phoneNumber.replace(/[^0-9]/g, '')
    if (cleanPhone.startsWith('0')) cleanPhone = '98' + cleanPhone.substring(1)
    // اگر شماره با 98 شروع نمی‌شود و 10 رقمی است، 98 اضافه کن (ایران)
    if (cleanPhone.length === 10 && !cleanPhone.startsWith('98')) {
        cleanPhone = '98' + cleanPhone
    }
    
    for (let i = 0; i < retries; i++) {
        try {
            console.log(`🔑 Trying pairing code for ${cleanPhone} attempt ${i+1}/${retries}`)
            const code = await sock.requestPairingCode(cleanPhone)
            console.log(`🔑 Pairing code success: ${code} for ${cleanPhone}`)
            return code
        } catch (e) {
            console.error(`❌ Pairing code attempt ${i+1} failed: ${e.message}`)
            if (i < retries - 1) {
                await new Promise(r => setTimeout(r, 2000))
            }
        }
    }
    return null
}

app.get('/', (req, res) => {
    const list = Object.keys(sessions).map(uid => ({ userId: uid, connected: sessions[uid].isConnected, hasQR: !!sessions[uid].qr, hasCode: !!sessions[uid].pairingCode, phone: sessions[uid].phoneNumber }))
    res.json({ status: 'ok', service: 'whatsapp-simple-with-code', uptime: process.uptime(), sessionsCount: list.length, sessions: list })
})

app.get('/qr', async (req, res) => {
    const userId = req.query.userId || req.query.user_id
    const phone = req.query.phone || null
    if (!userId) return res.status(400).json({ ok: false, error: 'userId required' })
    try {
        let session = sessions[String(userId)]
        if (!session) {
            console.log(`🆕 New QR request for ${userId} phone=${phone}`)
            session = await createSession(userId, phone)
            let attempts = 0
            while (!session.qr && !session.isConnected && attempts < 40) { await new Promise(r => setTimeout(r, 500)); attempts++ }
        } else {
            if (phone) session.phoneNumber = phone
        }

        // اگر متصل است
        if (session.isConnected) {
            return res.json({ ok: true, connected: true, userId: String(userId), phoneNumber: session.phoneNumber })
        }

        // اگر شماره دارد و کد ندارد، سعی کن کد بگیری (مهم برای نمایش کد کنار QR)
        if (phone && !session.pairingCode) {
            try {
                const code = await getPairingCodeWithRetry(session.sock, phone, 1)
                if (code) {
                    session.pairingCode = code
                    console.log(`🔑 Got pairing code in /qr for ${userId}: ${code}`)
                }
            } catch (e) {
                console.error(`Pairing code in /qr error: ${e.message}`)
            }
        }

        // اگر QR دارد، برگردان با کد (اگر دارد)
        if (session.qr) {
            return res.json({ 
                ok: true, 
                connected: false, 
                hasQR: true, 
                qr: session.qr, 
                qrImage: session.qrImage,
                pairingCode: session.pairingCode, // ممکن است null باشد اگر هنوز آماده نشده - مهم نیست، QR کار می‌کند
                userId: String(userId),
                phoneNumber: session.phoneNumber,
                instructions: 'Scan QR or enter pairing code in WhatsApp'
            })
        }

        return res.json({ ok: false, connected: false, hasQR: false, error: 'QR not ready, try again in 2s', userId: String(userId), pairingCode: session.pairingCode })
    } catch (e) {
        console.error(`QR error: ${e}`)
        res.status(500).json({ ok: false, error: e.message })
    }
})

app.get('/qr-image', async (req, res) => {
    const userId = req.query.userId || req.query.user_id
    const session = sessions[String(userId)]
    if (!session || !session.qrImage) return res.status(404).json({ ok: false, error: 'QR not ready, call /qr first' })
    try {
        const base64Data = session.qrImage.replace(/^data:image\/png;base64,/, '')
        const imgBuffer = Buffer.from(base64Data, 'base64')
        res.set('Content-Type', 'image/png')
        res.send(imgBuffer)
    } catch (e) { res.status(500).json({ ok: false, error: e.message }) }
})

app.get('/status', async (req, res) => {
    const userId = req.query.userId || req.query.user_id
    if (!userId) return res.json({ ok: true, count: Object.keys(sessions).length, sessions: Object.keys(sessions).map(uid => ({ userId: uid, connected: sessions[uid].isConnected, hasQR: !!sessions[uid].qr, hasCode: !!sessions[uid].pairingCode, pairingCode: sessions[uid].pairingCode })) })
    let session = sessions[String(userId)]
    if (!session) {
        // Check if auth folder exists - if yes, session exists on disk but not in memory
        const authFolder = path.join('auth', String(userId))
        if (fs.existsSync(authFolder)) {
            console.log(`♻️ Status check: ${userId} not in memory but auth exists, restoring...`)
            try {
                session = await createSession(String(userId))
                // Don't wait too long for status check
                let attempts = 0
                while (!session.isConnected && !session.qr && attempts < 10) {
                    await new Promise(r => setTimeout(r, 500))
                    attempts++
                }
            } catch (e) {
                console.error(`❌ Restore failed for status ${userId}: ${e}`)
            }
        }
    }
    if (!session) return res.json({ ok: false, connected: false, exists: false, userId: String(userId) })
    res.json({ ok: true, connected: session.isConnected, exists: true, hasQR: !!session.qr, hasCode: !!session.pairingCode, pairingCode: session.pairingCode, phone: session.phoneNumber, userId: String(userId) })
})

app.get('/chats', async (req, res) => {
    const userId = req.query.userId || req.query.user_id
    if (!userId) return res.status(400).json({ ok: false, error: 'userId required' })
    let session = sessions[String(userId)]
    if (!session) {
        const authFolder = path.join('auth', String(userId))
        if (fs.existsSync(authFolder)) {
            console.log(`♻️ Chats: ${userId} not in memory but auth exists, restoring...`)
            try {
                session = await createSession(String(userId))
                let attempts = 0
                while (!session.isConnected && attempts < 20) {
                    await new Promise(r => setTimeout(r, 500))
                    attempts++
                }
            } catch (e) {
                console.error(`❌ Restore failed for chats ${userId}: ${e}`)
            }
        }
    }
    if (!session) return res.status(404).json({ ok: false, error: 'Session not found - please reconnect WhatsApp via QR' })
    if (!session.isConnected) return res.status(400).json({ ok: false, error: 'Not connected - please scan QR', connected: false, exists: true })
    try {
        const sock = session.sock
        // Get all chats - groups and contacts
        const chats = []
        
        // Try to get groups
        try {
            const groups = await sock.groupFetchAllParticipating()
            for (const [id, group] of Object.entries(groups)) {
                chats.push({
                    id: id,
                    name: group.subject || id,
                    type: 'group',
                    participants: group.participants?.length || 0,
                    isGroup: true
                })
            }
        } catch (e) {
            console.log(`Group fetch error for ${userId}: ${e.message}`)
        }
        
        // Also try to get contacts from store if available
        // For Baileys, we can list recent chats from the session
        // As fallback, return groups only
        
        res.json({ 
            ok: true, 
            connected: true,
            chats: chats,
            count: chats.length,
            userId: String(userId),
            message: chats.length > 0 ? `Found ${chats.length} groups` : 'No groups found, you can still send to phone numbers'
        })
    } catch (e) {
        console.error(`Chats error for ${userId}: ${e}`)
        res.status(500).json({ ok: false, error: e.message })
    }
})

app.get('/qr-check', (req, res) => {
    const userId = req.query.userId || req.query.user_id
    const lastQR = req.query.lastQR || ''
    if (!userId) return res.status(400).json({ ok: false, error: 'userId required' })
    const session = sessions[String(userId)]
    if (!session) return res.json({ ok: false, exists: false })
    if (session.isConnected) return res.json({ ok: true, connected: true, changed: false })
    const changed = session.qr && session.qr !== lastQR
    res.json({ ok: true, connected: false, changed: changed, hasQR: !!session.qr, qr: changed ? session.qr : null, qrImage: changed ? session.qrImage : null, pairingCode: session.pairingCode, userId: String(userId) })
})

app.get('/pairing-code', async (req, res) => {
    const userId = req.query.userId || req.query.user_id
    const phone = req.query.phone
    if (!userId || !phone) return res.status(400).json({ ok: false, error: 'userId and phone required' })
    const session = sessions[String(userId)]
    if (!session) return res.status(404).json({ ok: false, error: 'Session not found, call /qr first' })
    try {
        const code = await getPairingCodeWithRetry(session.sock, phone, 2)
        if (code) {
            session.pairingCode = code
            session.phoneNumber = phone
            return res.json({ ok: true, pairingCode: code, userId: String(userId), phone })
        } else {
            return res.status(500).json({ ok: false, error: 'Failed to get pairing code after retries' })
        }
    } catch (e) {
        res.status(500).json({ ok: false, error: e.message })
    }
})

app.post('/connect', async (req, res) => {
    const { userId, phoneNumber, phone } = req.body
    const finalUserId = userId || req.body.user_id
    const finalPhone = phoneNumber || phone
    if (!finalUserId) return res.status(400).json({ ok: false, error: 'userId required' })
    try {
        const session = await createSession(finalUserId, finalPhone)
        let attempts = 0
        while (!session.qr && !session.isConnected && attempts < 40) { await new Promise(r => setTimeout(r, 500)); attempts++ }
        
        // سعی کن کد هم بگیری
        if (finalPhone && !session.pairingCode) {
            try {
                const code = await getPairingCodeWithRetry(session.sock, finalPhone, 1)
                if (code) session.pairingCode = code
            } catch(e) {}
        }
        
        if (session.isConnected) return res.json({ ok: true, connected: true, userId: String(finalUserId) })
        if (session.qr) return res.json({ ok: true, connected: false, hasQR: true, qr: session.qr, qrImage: session.qrImage, pairingCode: session.pairingCode, userId: String(finalUserId) })
        res.json({ ok: false, message: 'QR not ready' })
    } catch (e) { res.status(500).json({ ok: false, error: e.message }) }
})

app.delete('/session', async (req, res) => {
    const userId = req.query.userId || req.query.user_id || req.body?.userId
    const session = sessions[String(userId)]
    if (session) { try { await session.sock.logout() } catch(e) {} try { fs.rmSync(path.join('auth', String(userId)), { recursive: true, force: true }) } catch(e) {} delete sessions[String(userId)] }
    res.json({ ok: true })
})

app.post('/send', async (req, res) => {
    const { to, text, imageBase64, userId, user_id } = req.body
    const finalUserId = userId || user_id
    let session = sessions[String(finalUserId)]
    
    // اگر هیچ سشنی در حافظه نیست، سعی کن همه را از دیسک بازگردانی کنی
    if (Object.keys(sessions).length === 0) {
        console.log(`⚠️ No sessions in memory at all, trying to restore from disk...`)
        try {
            await restoreSessionsFromDisk()
            // Wait a bit
            await new Promise(r => setTimeout(r, 3000))
            session = sessions[String(finalUserId)]
        } catch (e) {
            console.error(`❌ Restore all failed: ${e}`)
        }
    }
    
    // اگر سشن در حافظه نیست ولی پوشه auth وجود دارد، سعی کن بازگردانی کنی
    if (!finalUserId || !session) {
        const authFolder = path.join('auth', String(finalUserId))
        if (fs.existsSync(authFolder)) {
            console.log(`♻️ Session ${finalUserId} not in memory but auth exists (${fs.readdirSync(authFolder).length} files), restoring...`)
            try {
                session = await createSession(finalUserId)
                // Wait for connection - longer
                let attempts = 0
                while (!session.isConnected && attempts < 30) {
                    await new Promise(r => setTimeout(r, 500))
                    attempts++
                    if (attempts % 10 === 0) console.log(`⏳ Waiting for ${finalUserId} connection... ${attempts*0.5}s`)
                }
                console.log(`📊 After restore: connected=${session.isConnected} for ${finalUserId}`)
            } catch (e) {
                console.error(`❌ Failed to restore session ${finalUserId}: ${e}`)
            }
        }
        if (!session) {
            return res.status(404).json({ ok: false, error: `Session ${finalUserId} not found - please reconnect WhatsApp via QR. Auth folder exists: ${fs.existsSync(path.join('auth', String(finalUserId)))}` })
        }
    }
    
    if (!session.isConnected) return res.status(503).json({ ok: false, error: 'Not connected - please scan QR again' })
    if (!to) return res.status(400).json({ ok: false, error: 'to required' })
    // نرمال‌سازی مقصد - گروه @g.us یا شخصی @s.whatsapp.net
    let finalTo = to
    if (to) {
        if (to.includes('@g.us') || to.includes('@s.whatsapp.net')) {
            finalTo = to
        } else if (/^\d+$/.test(to)) {
            // اگر 15+ رقم و با 120363 شروع می‌شود، گروه است
            if (to.startsWith('120363') || to.length > 15) {
                finalTo = `${to}@g.us`
            } else {
                finalTo = `${to}@s.whatsapp.net`
            }
        } else {
            // اگر فرمت دیگری دارد، همان را نگه دار
            finalTo = to
        }
    }
    
    try {
        await new Promise(r => setTimeout(r, 500))
        let result
        const { mediaType } = req.body
        
        if (imageBase64) {
            const buffer = Buffer.from(imageBase64, 'base64')
            if (mediaType === 'video') {
                result = await session.sock.sendMessage(finalTo, { video: buffer, caption: text || '' })
                console.log(`✅ Sent video to ${finalTo} via ${finalUserId}`)
            } else if (mediaType === 'document') {
                result = await session.sock.sendMessage(finalTo, { document: buffer, mimetype: 'application/octet-stream', fileName: 'file', caption: text || '' })
                console.log(`✅ Sent document to ${finalTo} via ${finalUserId}`)
            } else {
                // پیش‌فرض عکس
                result = await session.sock.sendMessage(finalTo, { image: buffer, caption: text || '' })
                console.log(`✅ Sent image to ${finalTo} via ${finalUserId}`)
            }
        } else {
            result = await session.sock.sendMessage(finalTo, { text: text || 'Hi' })
            console.log(`✅ Sent text to ${finalTo} via ${finalUserId}`)
        }
        res.json({ ok: true, messageId: result.key.id, to: finalTo })
    } catch(e) {
        console.error(`❌ Send error to ${finalTo} via ${finalUserId}: ${e}`)
        res.status(500).json({ ok: false, error: e.message, to: finalTo })
    }
})

app.listen(PORT, '0.0.0.0', async () => {
    console.log(`🚀 WhatsApp with pairing code on 0.0.0.0:${PORT}`)
    console.log(`✅ Ready - QR + pairing code!`)
    console.log(`📱 QR: http://localhost:${PORT}/qr?userId=xxx&phone=989...`)
    // Restore sessions from disk on startup
    setTimeout(() => {
        restoreSessionsFromDisk()
    }, 2000)
})
