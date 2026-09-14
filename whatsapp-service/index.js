const crypto = require('crypto')
global.crypto = crypto

const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys')
const express = require('express')
const qrcodeTerminal = require('qrcode-terminal')
const QRCode = require('qrcode')
const pino = require('pino')
const fs = require('fs')
const path = require('path')

process.on('uncaughtException', (err) => { console.error(`💥 Uncaught Exception: ${err.message}\n${err.stack}`) })
process.on('unhandledRejection', (reason) => { console.error(`💥 Unhandled Rejection:`, reason instanceof Error ? reason.message + '\n' + reason.stack : reason) })

const app = express()
app.use(express.json({limit: '50mb'}))
const PORT = 3001
const logger = pino({ level: 'silent' })
const sessions = {}
const AUTH_BASE_DIR = path.join(__dirname, 'auth')
const SESSIONS_DB_FILE = path.join(__dirname, 'sessions_db.json')
const BACKUP_BASE_DIR = path.join(__dirname, '..', 'all_pg_agnet', 'AGENT-MANAGER_BOTS_MASSENGER', 'users')

function loadSessionsDB() {
    try {
        if (fs.existsSync(SESSIONS_DB_FILE)) {
            const data = JSON.parse(fs.readFileSync(SESSIONS_DB_FILE, 'utf-8'))
            console.log(`📂 Loaded sessions DB: ${Object.keys(data).length} entries`)
            return data
        }
    } catch (e) { console.error(`❌ Failed to load sessions DB: ${e}`) }
    return {}
}
function saveSessionsDB(db) { try { fs.writeFileSync(SESSIONS_DB_FILE, JSON.stringify(db, null, 2), 'utf-8') } catch (e) { console.error(`❌ Failed to save sessions DB: ${e}`) } }
function updateSessionInDB(userId, info) {
    try {
        const db = loadSessionsDB()
        db[String(userId)] = { ...db[String(userId)], ...info, userId: String(userId), lastUpdate: new Date().toISOString(), authPath: path.join(AUTH_BASE_DIR, String(userId)), authExists: fs.existsSync(path.join(AUTH_BASE_DIR, String(userId))), authFiles: fs.existsSync(path.join(AUTH_BASE_DIR, String(userId))) ? fs.readdirSync(path.join(AUTH_BASE_DIR, String(userId))).length : 0 }
        saveSessionsDB(db)
        try {
            if (fs.existsSync(BACKUP_BASE_DIR)) {
                const userBackupInfoFile = path.join(BACKUP_BASE_DIR, String(userId), 'whatsapp_session_info.json')
                fs.mkdirSync(path.dirname(userBackupInfoFile), { recursive: true })
                fs.writeFileSync(userBackupInfoFile, JSON.stringify(db[String(userId)], null, 2), 'utf-8')
            }
        } catch (e) {}
    } catch (e) { console.error(`❌ updateSessionInDB error: ${e}`) }
}
function deleteSessionFromDB(userId) { try { const db = loadSessionsDB(); if (db[String(userId)]) { delete db[String(userId)]; saveSessionsDB(db); console.log(`🗑️ Deleted ${userId} from sessions DB`) } } catch (e) { console.error(`❌ deleteSessionFromDB error: ${e}`) } }
function backupAuthFolder(userId) {
    try {
        const authFolder = path.join(AUTH_BASE_DIR, String(userId))
        if (!fs.existsSync(authFolder)) return
        if (fs.existsSync(BACKUP_BASE_DIR)) {
            const backupDir = path.join(BACKUP_BASE_DIR, String(userId), 'whatsapp_auth_backup', String(userId))
            fs.mkdirSync(backupDir, { recursive: true })
            const files = fs.readdirSync(authFolder)
            for (const file of files) { try { const src = path.join(authFolder, file); const dest = path.join(backupDir, file); if (fs.statSync(src).isFile()) fs.copyFileSync(src, dest) } catch (e) {} }
            console.log(`💾 Backed up ${files.length} auth files for ${userId}`)
        }
    } catch (e) { console.error(`❌ backupAuthFolder error for ${userId}: ${e}`) }
}
function restoreFromUserBackup(userId) {
    try {
        const backupDir = path.join(BACKUP_BASE_DIR, String(userId), 'whatsapp_auth_backup', String(userId))
        const authFolder = path.join(AUTH_BASE_DIR, String(userId))
        if (fs.existsSync(backupDir) && !fs.existsSync(authFolder)) {
            console.log(`♻️ Restoring auth from user backup: ${backupDir} -> ${authFolder}`)
            fs.mkdirSync(authFolder, { recursive: true })
            const files = fs.readdirSync(backupDir)
            for (const file of files) { try { fs.copyFileSync(path.join(backupDir, file), path.join(authFolder, file)) } catch (e) {} }
            console.log(`✅ Restored ${files.length} files from user backup for ${userId}`)
            return true
        }
    } catch (e) { console.error(`❌ restoreFromUserBackup error for ${userId}: ${e}`) }
    return false
}
function fullyDeleteSession(userId, deleteBackup = false) {
    const userIdStr = String(userId)
    console.log(`🗑️ Fully deleting session ${userIdStr} - deleteBackup=${deleteBackup}`)
    try {
        const session = sessions[userIdStr]
        if (session && session.sock) {
            try {
                const wsState = session.sock.ws?.readyState
                if (wsState === 1) { try { session.sock.end(undefined) } catch(e) {} } else { try { session.sock.ws?.close() } catch(e) {} }
                try { session.sock.ev?.removeAllListeners?.('connection.update') } catch(e) {}
                try { session.sock.ev?.removeAllListeners?.('creds.update') } catch(e) {}
            } catch(e) {}
        }
    } catch(e) {}
    try { delete sessions[userIdStr] } catch(e) {}
    try { const authFolder = path.join(AUTH_BASE_DIR, userIdStr); if (fs.existsSync(authFolder)) { fs.rmSync(authFolder, { recursive: true, force: true }); console.log(`🗑️ Deleted auth folder ${authFolder}`) } } catch(e) { console.error(`❌ Failed to delete auth folder for ${userIdStr}: ${e}`) }
    try { deleteSessionFromDB(userIdStr) } catch(e) {}
    if (deleteBackup) {
        try {
            const backupDir = path.join(BACKUP_BASE_DIR, userIdStr, 'whatsapp_auth_backup', userIdStr)
            if (fs.existsSync(backupDir)) { fs.rmSync(backupDir, { recursive: true, force: true }); console.log(`🗑️ Deleted backup folder ${backupDir}`) }
            const backupParent = path.join(BACKUP_BASE_DIR, userIdStr, 'whatsapp_auth_backup')
            if (fs.existsSync(backupParent) && fs.readdirSync(backupParent).length === 0) { fs.rmdirSync(backupParent) }
        } catch(e) { console.error(`❌ Failed to delete backup for ${userIdStr}: ${e}`) }
    }
    console.log(`✅ Fully deleted session ${userIdStr} - ready for fresh QR (backupDeleted=${deleteBackup})`)
}
async function restoreSessionsFromDisk() {
    try {
        const authDir = AUTH_BASE_DIR
        if (!fs.existsSync(authDir)) fs.mkdirSync(authDir, { recursive: true })
        const db = loadSessionsDB()
        console.log(`📂 Sessions DB has ${Object.keys(db).length} entries: ${Object.keys(db).join(', ')}`)
        for (const userId of Object.keys(db)) { const authPath = path.join(authDir, userId); if (!fs.existsSync(authPath)) { console.log(`⚠️ Auth folder missing for ${userId} from DB, trying user backup...`); restoreFromUserBackup(userId) } }
        if (fs.existsSync(BACKUP_BASE_DIR)) {
            try {
                const userFolders = fs.readdirSync(BACKUP_BASE_DIR)
                for (const userId of userFolders) {
                    const backupAuthPath = path.join(BACKUP_BASE_DIR, userId, 'whatsapp_auth_backup', userId)
                    const mainAuthPath = path.join(authDir, userId)
                    if (fs.existsSync(backupAuthPath) && !fs.existsSync(mainAuthPath)) {
                        console.log(`♻️ Found backup for ${userId} in users folder, restoring`)
                        fs.mkdirSync(mainAuthPath, { recursive: true })
                        const files = fs.readdirSync(backupAuthPath)
                        for (const file of files) { try { fs.copyFileSync(path.join(backupAuthPath, file), path.join(mainAuthPath, file)) } catch(e) {} }
                    }
                }
            } catch (e) {}
        }
        if (!fs.existsSync(authDir)) return
        const userDirs = fs.readdirSync(authDir)
        console.log(`🔄 Found ${userDirs.length} auth folders to restore: ${userDirs.join(', ')}`)
        for (const userId of userDirs) {
            const userAuthPath = path.join(authDir, userId)
            try {
                if (fs.statSync(userAuthPath).isDirectory()) {
                    const files = fs.readdirSync(userAuthPath)
                    if (files.length >= 2) {
                        console.log(`♻️ Restoring session for ${userId} (${files.length} files)`)
                        try { await createSession(userId) } catch (e) { console.error(`❌ Restore createSession failed for ${userId}: ${e.message}`) }
                        await new Promise(r => setTimeout(r, 3000))
                    } else { console.log(`⚠️ Empty/corrupted auth folder for ${userId} (${files.length} files), deleting`); fullyDeleteSession(userId, false) }
                }
            } catch (e) { console.error(`❌ Failed to restore ${userId}: ${e.message}`) }
        }
        console.log(`✅ Restore done, ${Object.keys(sessions).length} sessions in memory`)
        for (const userId of Object.keys(sessions)) { try { updateSessionInDB(userId, { connected: sessions[userId].isConnected, restoredAt: new Date().toISOString() }) } catch(e) {} }
    } catch (e) { console.error(`❌ restoreSessionsFromDisk error: ${e} ${e.stack}`) }
}

async function createSession(userId, phoneNumber = null, force = false) {
    const userIdStr = String(userId)
    console.log(`🔧 Creating session for ${userIdStr} phone=${phoneNumber} force=${force} authBase=${AUTH_BASE_DIR}`)

    if (force) {
        console.log(`🔥 Force flag - fully deleting old session ${userIdStr} before creating new (with backup delete)`)
        fullyDeleteSession(userIdStr, true)
        await new Promise(r => setTimeout(r, 800))
    }

    if (sessions[userIdStr] && sessions[userIdStr].isConnected && !force) {
        console.log(`♻️ Session ${userIdStr} already connected, returning existing (use force=true to recreate)`)
        updateSessionInDB(userIdStr, { connected: true, phoneNumber, lastCreate: new Date().toISOString() })
        return sessions[userIdStr]
    }
    if (sessions[userIdStr] && sessions[userIdStr].sock) { 
        try { console.log(`🔄 Closing existing sock for ${userIdStr}`); const wsState = sessions[userIdStr].sock.ws?.readyState; if (wsState === 1) sessions[userIdStr].sock.end(undefined) } catch(e) {} 
    }
    
    const authFolderCheck = path.join(AUTH_BASE_DIR, userIdStr)
    if (!force && !fs.existsSync(authFolderCheck)) { restoreFromUserBackup(userIdStr) }
    else if (force && fs.existsSync(authFolderCheck)) { console.log(`⚠️ Force=true but auth folder still exists for ${userIdStr}, deleting again`); try { fs.rmSync(authFolderCheck, { recursive: true, force: true }) } catch(e) {} }
    
    const authFolder = path.join(AUTH_BASE_DIR, userIdStr)
    updateSessionInDB(userIdStr, { phoneNumber, authPath: authFolder, creating: true })
    if (!fs.existsSync(authFolder)) fs.mkdirSync(authFolder, { recursive: true })

    let state, saveCreds
    try {
        const auth = await useMultiFileAuthState(authFolder)
        state = auth.state
        saveCreds = auth.saveCreds
    } catch (e) {
        console.error(`❌ useMultiFileAuthState failed for ${userIdStr}: ${e.message} - deleting corrupted folder`)
        try { fs.rmSync(authFolder, { recursive: true, force: true }) } catch(e2) {}
        fs.mkdirSync(authFolder, { recursive: true })
        const auth2 = await useMultiFileAuthState(authFolder)
        state = auth2.state
        saveCreds = auth2.saveCreds
    }

    let version
    try { const v = await fetchLatestBaileysVersion(); version = v.version } catch (e) { version = [2, 3000, 1023223821] }
    console.log(`📦 Baileys version ${version} for ${userIdStr}`)

    const sessionPlaceholder = { groups: {} }
    let sock
    try {
        sock = makeWASocket({ 
            version, 
            auth: state, 
            logger, 
            printQRInTerminal: false, 
            browser: ['Ubuntu', 'Chrome', '20.0.04'],
            markOnlineOnConnect: false,
            syncFullHistory: false,
            getMessage: async (key) => undefined,
            cachedGroupMetadata: async (jid) => {
                try {
                    const memSession = sessions[userIdStr]
                    if (memSession && memSession.groups && memSession.groups[jid]) return memSession.groups[jid]
                    if (sessionPlaceholder.groups[jid]) return sessionPlaceholder.groups[jid]
                    return undefined
                } catch { return undefined }
            }
        })
    } catch (e) {
        console.error(`❌ makeWASocket failed for ${userIdStr}: ${e.message} ${e.stack}`)
        await new Promise(r => setTimeout(r, 3000))
        throw e
    }

    const session = { sock, isConnected: false, qr: null, qrImage: null, pairingCode: null, phoneNumber, lastUpdate: new Date(), userId: userIdStr, lastQR: null, groups: {}, groupsCacheTime: null, lastGroupsFetch: null, forceReset: force, reconnectAttempts: 0 }
    sessions[userIdStr] = session

    try { sock.ev.on('creds.update', saveCreds) } catch (e) { console.error(`creds.update handler error: ${e}`) }

    try {
        sock.ev.on('groups.upsert', (groups) => {
            try {
                console.log(`📋 groups.upsert for ${userIdStr}: ${groups.length} groups`)
                for (const g of groups) { if (g.id) { session.groups[g.id] = g; sessionPlaceholder.groups[g.id] = g } }
                session.groupsCacheTime = new Date()
            } catch(e) {}
        })
        sock.ev.on('groups.update', (updates) => {
            try { for (const u of updates) { if (u.id && session.groups[u.id]) { session.groups[u.id] = { ...session.groups[u.id], ...u }; sessionPlaceholder.groups[u.id] = session.groups[u.id] } } } catch(e) {}
        })
        sock.ev.on('chats.upsert', (chats) => {
            try {
                for (const c of chats) {
                    if (c.id && c.id.endsWith('@g.us')) {
                        if (!session.groups[c.id]) { session.groups[c.id] = { id: c.id, subject: c.name || c.id, participants: [] }; sessionPlaceholder.groups[c.id] = session.groups[c.id] }
                    }
                }
            } catch(e) {}
        })
        // v7: listen for messages to auto-build sender keys
        sock.ev.on('messages.upsert', async (m) => {
            try {
                const msgs = m.messages || []
                for (const msg of msgs) {
                    if (msg.key?.remoteJid?.endsWith('@g.us')) {
                        console.log(`📩 Received group message in ${msg.key.remoteJid} - sender keys should now be available for group send`)
                    }
                }
            } catch(e) {}
        })
    } catch(e) { console.error(`groups handler setup error: ${e}`) }

    sock.ev.on('connection.update', async (update) => {
        try {
            const { connection, lastDisconnect, qr } = update
            session.lastUpdate = new Date()
            if (qr) {
                session.qr = qr
                session.lastQR = qr
                console.log(`📱 QR for ${userIdStr} - SCAN NOW!`)
                try { qrcodeTerminal.generate(qr, { small: true }) } catch(e) {}
                try { session.qrImage = await QRCode.toDataURL(qr, { width: 400, margin: 2 }) } catch(e) { console.error(`QR image gen failed: ${e}`) }
            }
            if (connection === 'close') {
                const statusCode = lastDisconnect?.error?.output?.statusCode || lastDisconnect?.error?.output?.payload?.statusCode
                const reason = lastDisconnect?.error?.message || 'unknown'
                const boomMessage = lastDisconnect?.error?.output?.payload?.message || reason
                console.log(`❌ Closed for ${userIdStr} code=${statusCode} reason=${reason} boom=${boomMessage}`)
                session.isConnected = false
                session.reconnectAttempts = (session.reconnectAttempts || 0) + 1

                if (statusCode === DisconnectReason.loggedOut || statusCode === 401) {
                    console.log(`🚫 Logged out ${userIdStr} - deleting auth AND backup, need fresh QR. Call /qr?force=true`)
                    try {
                        const authF = path.join(AUTH_BASE_DIR, userIdStr)
                        if (fs.existsSync(authF)) { fs.rmSync(authF, { recursive: true, force: true }) }
                        const backupDir = path.join(BACKUP_BASE_DIR, userIdStr, 'whatsapp_auth_backup', userIdStr)
                        if (fs.existsSync(backupDir)) { fs.rmSync(backupDir, { recursive: true, force: true }); console.log(`🗑️ Deleted corrupted backup for ${userIdStr} after 401`) }
                    } catch(e) {}
                    delete sessions[userIdStr]
                    try { deleteSessionFromDB(userIdStr) } catch(e) {}
                    return
                }

                if (session.reconnectAttempts > 5) { console.log(`⚠️ Too many reconnect attempts (${session.reconnectAttempts}) for ${userIdStr}, giving up - need fresh QR via /qr?force=true`); return }

                const delay = statusCode === 428 ? 5000 : 3000
                console.log(`🔄 Reconnect ${userIdStr} in ${delay/1000}s... code=${statusCode} attempt=${session.reconnectAttempts}`)
                setTimeout(() => { try { createSession(userIdStr, phoneNumber) } catch(e) { console.error(`Reconnect createSession error: ${e}`) } }, delay)

            } else if (connection === 'open') {
                console.log(`✅✅✅ CONNECTED for ${userIdStr}! ✅✅✅`)
                session.isConnected = true
                session.qr = null
                session.qrImage = null
                session.pairingCode = null
                session.forceReset = false
                session.reconnectAttempts = 0
                try { updateSessionInDB(userIdStr, { connected: true, phoneNumber, connectedAt: new Date().toISOString(), lastConnected: new Date().toISOString() }) } catch(e) {}
                setTimeout(() => { try { backupAuthFolder(userIdStr) } catch(e) {} }, 2000)
                setTimeout(async () => {
                    try {
                        console.log(`🔄 Auto-fetching groups for ${userIdStr} after connect...`)
                        const groups = await session.sock.groupFetchAllParticipating()
                        console.log(`✅ Auto-fetched ${Object.keys(groups).length} groups for ${userIdStr}`)
                        session.groups = { ...session.groups, ...groups }
                        session.groupsCacheTime = new Date()
                        session.lastGroupsFetch = new Date()
                    } catch (e) { console.log(`⚠️ Auto group fetch failed for ${userIdStr}: ${e.message}`) }
                }, 3000)
                try {
                    setTimeout(async () => {
                        try {
                            if (session.phoneNumber && !session.phoneNumber.includes('@g.us')) {
                                let testTo = session.phoneNumber
                                if (/^\d+$/.test(testTo)) testTo = `${testTo}@s.whatsapp.net`
                                await session.sock.sendMessage(testTo, { text: '✅ واتساپ متصل شد! اوکی وصله 🎉\n\nربات آماده ارسال پست است' })
                            }
                        } catch (e) {}
                    }, 3000)
                } catch (e) {}
            }
        } catch (e) { console.error(`❌ connection.update handler error for ${userIdStr}: ${e.message} ${e.stack}`) }
    })

    return session
}

async function getPairingCodeWithRetry(sock, phoneNumber, retries = 3) {
    if (!phoneNumber) return null
    let cleanPhone = phoneNumber.replace(/[^0-9]/g, '')
    if (cleanPhone.startsWith('0')) cleanPhone = '98' + cleanPhone.substring(1)
    if (cleanPhone.length === 10 && cleanPhone.startsWith('9')) cleanPhone = '98' + cleanPhone
    if (cleanPhone.length === 11 && cleanPhone.startsWith('09')) cleanPhone = '98' + cleanPhone.substring(1)
    if (cleanPhone.length < 10) return null
    for (let i = 0; i < retries; i++) {
        try {
            const code = await sock.requestPairingCode(cleanPhone)
            console.log(`✅ Pairing code success: ${code} for ${cleanPhone}`)
            return code
        } catch (e) {
            console.error(`❌ Pairing code attempt ${i+1} failed for ${cleanPhone}: ${e.message}`)
            if (i < retries - 1) await new Promise(r => setTimeout(r, 2000))
        }
    }
    return null
}

app.get('/', (req, res) => {
    try {
        const list = Object.keys(sessions).map(uid => ({ userId: uid, connected: sessions[uid].isConnected, hasQR: !!sessions[uid].qr, hasCode: !!sessions[uid].pairingCode, phone: sessions[uid].phoneNumber, groups: Object.keys(sessions[uid].groups||{}).length }))
        res.json({ status: 'ok', service: 'whatsapp-fixed-v7-baileys7', uptime: process.uptime(), sessionsCount: list.length, sessions: list })
    } catch (e) { res.json({ status: 'ok', service: 'whatsapp-fixed-v7-baileys7', uptime: process.uptime(), error: e.message }) }
})

app.get('/qr', async (req, res) => {
    const userId = req.query.userId || req.query.user_id
    const phone = req.query.phone || null
    const ownPhone = req.query.ownPhone || req.query.own_phone || phone || null
    const force = req.query.force === 'true' || req.query.force === '1'
    const deleteBackup = req.query.deleteBackup === 'true' || req.query.deleteBackup === '1' || force
    if (!userId) return res.status(400).json({ ok: false, error: 'userId required' })
    try {
        let session = sessions[String(userId)]
        if (force) { console.log(`🔥 /qr force=true for ${userId} - deleting old session + backup=${deleteBackup}`); fullyDeleteSession(userId, deleteBackup); session = null }
        if (!session) {
            console.log(`🆕 New QR request for ${userId} phone=${phone} ownPhone=${ownPhone} force=${force}`)
            session = await createSession(userId, ownPhone || phone, force)
            let attempts = 0
            while (!session.qr && !session.isConnected && attempts < 40) { await new Promise(r => setTimeout(r, 500)); attempts++ }
        } else {
            if (ownPhone) session.phoneNumber = ownPhone
            else if (phone) session.phoneNumber = phone
            updateSessionInDB(String(userId), { phoneNumber: session.phoneNumber, lastQRRequest: new Date().toISOString() })
        }

        if (session.isConnected && !force) { return res.json({ ok: true, connected: true, userId: String(userId), phoneNumber: session.phoneNumber }) }

        const phoneForCode = ownPhone || phone || session.phoneNumber
        if (phoneForCode && !session.pairingCode) {
            try { const code = await getPairingCodeWithRetry(session.sock, phoneForCode, 2); if (code) { session.pairingCode = code; updateSessionInDB(String(userId), { pairingCode: code, phoneForCode }) } } catch (e) {}
        }

        if (session.qr) {
            return res.json({ ok: true, connected: false, hasQR: true, qr: session.qr, qrImage: session.qrImage, pairingCode: session.pairingCode, pairingCodePlain: session.pairingCode ? session.pairingCode.replace(/-/g, '') : null, pairingCodeFormatted: session.pairingCode, userId: String(userId), phoneNumber: session.phoneNumber, phoneForPairing: phoneForCode, instructions: 'Scan QR or enter pairing code', copyableCode: session.pairingCode, howTo: { qr: 'WhatsApp -> Settings -> Linked Devices -> Link a Device -> Scan QR', code: `WhatsApp -> Settings -> Linked Devices -> Link with phone number -> Enter code: ${session.pairingCode}` } })
        }
        return res.json({ ok: false, connected: false, hasQR: false, error: 'QR not ready, try again in 2s', userId: String(userId), pairingCode: session.pairingCode })
    } catch (e) { console.error(`QR error: ${e} ${e.stack}`); res.status(500).json({ ok: false, error: e.message }) }
})

app.get('/qr-image', async (req, res) => {
    const userId = req.query.userId || req.query.user_id
    const session = sessions[String(userId)]
    if (!session || !session.qrImage) return res.status(404).json({ ok: false, error: 'QR not ready, call /qr first' })
    try { const base64Data = session.qrImage.replace(/^data:image\/png;base64,/, ''); const imgBuffer = Buffer.from(base64Data, 'base64'); res.set('Content-Type', 'image/png'); res.send(imgBuffer) } catch (e) { res.status(500).json({ ok: false, error: e.message }) }
})

app.get('/status', async (req, res) => {
    const userId = req.query.userId || req.query.user_id
    if (!userId) return res.json({ ok: true, count: Object.keys(sessions).length, sessions: Object.keys(sessions).map(uid => ({ userId: uid, connected: sessions[uid].isConnected, hasQR: !!sessions[uid].qr, hasCode: !!sessions[uid].pairingCode, pairingCode: sessions[uid].pairingCode, groups: Object.keys(sessions[uid].groups||{}).length })), authBase: AUTH_BASE_DIR, authExists: fs.existsSync(AUTH_BASE_DIR), authFolders: fs.existsSync(AUTH_BASE_DIR) ? fs.readdirSync(AUTH_BASE_DIR) : [] })
    let session = sessions[String(userId)]
    if (!session) {
        const authFolder = path.join(AUTH_BASE_DIR, String(userId))
        if (fs.existsSync(authFolder)) {
            const files = fs.readdirSync(authFolder)
            if (files.length < 2) { console.log(`⚠️ Auth folder empty/corrupted for ${userId} at ${authFolder} - deleting`); fullyDeleteSession(userId, false); return res.json({ ok: false, connected: false, exists: false, empty: true, userId: String(userId), message: 'Auth folder empty - deleted, ready for fresh QR. Call /qr?force=true' }) }
            console.log(`♻️ Status check: ${userId} not in memory but auth exists (${files.length} files), restoring...`)
            try { session = await createSession(String(userId)); let attempts = 0; while (!session.isConnected && !session.qr && attempts < 10) { await new Promise(r => setTimeout(r, 500)); attempts++ } } catch (e) { console.error(`❌ Restore failed for status ${userId}: ${e} ${e.stack}`) }
        }
    }
    if (!session) return res.json({ ok: false, connected: false, exists: false, userId: String(userId), authExists: fs.existsSync(path.join(AUTH_BASE_DIR, String(userId))) })
    res.json({ ok: true, connected: session.isConnected, exists: true, hasQR: !!session.qr, hasCode: !!session.pairingCode, pairingCode: session.pairingCode, phone: session.phoneNumber, userId: String(userId), groups: Object.keys(session.groups||{}).length })
})

app.get('/chats', async (req, res) => {
    const userId = req.query.userId || req.query.user_id
    if (!userId) return res.status(400).json({ ok: false, error: 'userId required' })
    let session = sessions[String(userId)]
    if (!session) {
        const authFolder = path.join(AUTH_BASE_DIR, String(userId))
        if (fs.existsSync(authFolder)) {
            try { session = await createSession(String(userId)); let attempts = 0; while (!session.isConnected && attempts < 20) { await new Promise(r => setTimeout(r, 500)); attempts++ } } catch (e) {}
        }
    }
    if (!session) return res.status(404).json({ ok: false, error: 'Session not found - please reconnect WhatsApp via QR', code: 'SESSION_NOT_FOUND' })
    if (!session.isConnected) return res.status(400).json({ ok: false, error: 'Not connected - please scan QR', connected: false, exists: true, code: 'NOT_CONNECTED' })
    try {
        const sock = session.sock
        const chats = []
        let groups = {}
        let lastError = null
        let fetchedVia = 'fetch'
        for (let attempt = 1; attempt <= 10; attempt++) {
            try {
                groups = await sock.groupFetchAllParticipating()
                const count = Object.keys(groups).length
                if (count > 0) { session.groups = { ...session.groups, ...groups }; session.lastGroupsFetch = new Date(); break }
                if (Object.keys(session.groups||{}).length > 0) { groups = session.groups; fetchedVia = 'cache_during_fetch'; break }
                if (attempt < 10) await new Promise(r => setTimeout(r, 3000))
            } catch (e) { lastError = e; if (attempt < 10) await new Promise(r => setTimeout(r, 2000)) }
        }
        if (Object.keys(groups).length === 0 && session.groups && Object.keys(session.groups).length > 0) { groups = session.groups; fetchedVia = 'cache_after_fetch' }
        try { for (const [id, group] of Object.entries(groups)) { chats.push({ id: id, name: group.subject || group.name || id, type: 'group', participants: group.participants?.length || group.participantsCount || 0, isGroup: true }) } } catch (e) {}
        res.json({ ok: true, connected: true, chats: chats, count: chats.length, userId: String(userId), message: chats.length > 0 ? `Found ${chats.length} groups` : 'No groups found - wait 60s and try again or send group ID manually: 120363312386194255@g.us', debug: { lastError: lastError?.message || null, fetchedVia, cacheSize: Object.keys(session.groups||{}).length } })
    } catch (e) { res.status(500).json({ ok: false, error: e.message }) }
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
    const phone = req.query.phone || req.query.ownPhone || req.query.own_phone
    if (!userId || !phone) return res.status(400).json({ ok: false, error: 'userId and phone required' })
    let session = sessions[String(userId)]
    if (!session) {
        try { session = await createSession(String(userId), phone); let attempts = 0; while (!session.sock && attempts < 10) { await new Promise(r => setTimeout(r, 500)); attempts++ } } catch (e) { return res.status(500).json({ ok: false, error: `Failed to create session: ${e.message}` }) }
    }
    try {
        const code = await getPairingCodeWithRetry(session.sock, phone, 3)
        if (code) { session.pairingCode = code; session.phoneNumber = phone; updateSessionInDB(String(userId), { pairingCode: code, phoneNumber: phone }); return res.json({ ok: true, pairingCode: code, pairingCodePlain: code.replace(/-/g, ''), userId: String(userId), phone }) }
        else { return res.status(500).json({ ok: false, error: `Failed to get pairing code for ${phone}` }) }
    } catch (e) { res.status(500).json({ ok: false, error: e.message }) }
})

app.get('/pairing-code-text', async (req, res) => {
    const userId = req.query.userId || req.query.user_id
    const session = sessions[String(userId)]
    if (!session || !session.pairingCode) return res.status(404).send('No pairing code')
    res.set('Content-Type', 'text/plain; charset=utf-8'); res.send(session.pairingCode)
})

app.post('/connect', async (req, res) => {
    const { userId, phoneNumber, phone, force } = req.body
    const finalUserId = userId || req.body.user_id
    const finalPhone = phoneNumber || phone
    if (!finalUserId) return res.status(400).json({ ok: false, error: 'userId required' })
    try {
        const session = await createSession(finalUserId, finalPhone, force === true)
        let attempts = 0
        while (!session.qr && !session.isConnected && attempts < 40) { await new Promise(r => setTimeout(r, 500)); attempts++ }
        if (finalPhone && !session.pairingCode) { try { const code = await getPairingCodeWithRetry(session.sock, finalPhone, 1); if (code) session.pairingCode = code } catch(e) {} }
        if (session.isConnected) return res.json({ ok: true, connected: true, userId: String(finalUserId) })
        if (session.qr) return res.json({ ok: true, connected: false, hasQR: true, qr: session.qr, qrImage: session.qrImage, pairingCode: session.pairingCode, userId: String(finalUserId) })
        res.json({ ok: false, message: 'QR not ready' })
    } catch (e) { res.status(500).json({ ok: false, error: e.message }) }
})

app.delete('/session', async (req, res) => {
    const userId = req.query.userId || req.query.user_id || req.body?.userId
    const force = req.query.force === 'true' || req.query.force === '1' || req.body?.force === true
    const deleteBackup = req.query.deleteBackup === 'true' || req.query.deleteBackup === '1' || force
    if (!userId) return res.status(400).json({ ok: false, error: 'userId required' })
    console.log(`🗑️ DELETE /session for ${userId} force=${force} deleteBackup=${deleteBackup}`)
    try { fullyDeleteSession(userId, deleteBackup); res.json({ ok: true, deleted: true, userId: String(userId), force, deleteBackup, message: 'Session fully deleted - ready for fresh QR. Call /qr?force=true' }) } catch (e) { res.status(500).json({ ok: false, error: e.message }) }
})

app.post('/reset', async (req, res) => {
    const userId = req.body?.userId || req.query.userId || req.query.user_id
    const phone = req.body?.phone || req.query.phone
    if (!userId) return res.status(400).json({ ok: false, error: 'userId required' })
    console.log(`🔥 POST /reset for ${userId} phone=${phone} - force fresh QR (delete backup)`)
    try {
        fullyDeleteSession(userId, true)
        await new Promise(r => setTimeout(r, 1000))
        const session = await createSession(userId, phone, true)
        let attempts = 0
        while (!session.qr && !session.isConnected && attempts < 40) { await new Promise(r => setTimeout(r, 500)); attempts++ }
        if (session.qr) { return res.json({ ok: true, reset: true, hasQR: true, qr: session.qr, qrImage: session.qrImage, pairingCode: session.pairingCode, userId: String(userId), message: 'Old session deleted (including backup), new QR ready - scan now' }) }
        return res.json({ ok: true, reset: true, connected: session.isConnected, userId: String(userId), hasQR: !!session.qr })
    } catch (e) { console.error(`Reset error: ${e}`); res.status(500).json({ ok: false, error: e.message }) }
})

app.get('/restore', async (req, res) => {
    const userId = req.query.userId || req.query.user_id
    if (userId) {
        const authFolder = path.join(AUTH_BASE_DIR, String(userId))
        if (fs.existsSync(authFolder)) {
            const files = fs.readdirSync(authFolder)
            if (files.length < 2) { fullyDeleteSession(userId, false); return res.status(404).json({ ok: false, error: 'Auth folder empty - deleted, ready for fresh QR', empty: true, code: 'EMPTY_AUTH' }) }
            try { const session = await createSession(String(userId)); let attempts = 0; while (!session.isConnected && attempts < 20) { await new Promise(r => setTimeout(r, 500)); attempts++ }; return res.json({ ok: true, restored: true, connected: session.isConnected, userId: String(userId), files: files.length }) } catch (e) { return res.status(500).json({ ok: false, error: e.message }) }
        } else { return res.status(404).json({ ok: false, error: `Auth folder not found`, code: 'NOT_FOUND' }) }
    } else { await restoreSessionsFromDisk(); return res.json({ ok: true, sessions: Object.keys(sessions).length, list: Object.keys(sessions).map(uid => ({ userId: uid, connected: sessions[uid].isConnected })) }) }
})

app.post('/clean-sessions', async (req, res) => {
    const userId = req.body?.userId || req.query.userId || req.query.user_id
    const all = req.query.all === 'true' || req.body?.all === true
    if (!userId) return res.status(400).json({ ok: false, error: 'userId required' })
    try {
        const authFolder = path.join(AUTH_BASE_DIR, String(userId))
        if (!fs.existsSync(authFolder)) return res.status(404).json({ ok: false, error: 'Auth folder not found' })
        const files = fs.readdirSync(authFolder)
        let deleted = []
        for (const f of files) {
            if (all) {
                if (f.startsWith('session-') || f.startsWith('sender-key-')) { try { fs.rmSync(path.join(authFolder, f)); deleted.push(f) } catch(e) {} }
            } else {
                if (f.startsWith('sender-key-') || (f.startsWith('session-') && !f.includes('989038013654'))) { try { fs.rmSync(path.join(authFolder, f)); deleted.push(f) } catch(e) {} }
            }
        }
        console.log(`🧹 Cleaned ${deleted.length} files for ${userId} all=${all}`)
        try { const session = sessions[String(userId)]; if (session && session.sock) { try { session.sock.end(undefined) } catch(e) {} } delete sessions[String(userId)]; await new Promise(r => setTimeout(r, 1500)); await createSession(userId) } catch(e) { console.error(`Clean reconnect error: ${e}`) }
        res.json({ ok: true, deleted: deleted.length, files: deleted.slice(0,20), message: `Cleaned ${deleted.length} files all=${all}, reconnecting...` })
    } catch (e) { res.status(500).json({ ok: false, error: e.message }) }
})

app.post('/clean-all-sessions', async (req, res) => {
    const userId = req.body?.userId || req.query.userId || req.query.user_id
    if (!userId) return res.status(400).json({ ok: false, error: 'userId required' })
    try {
        const authFolder = path.join(AUTH_BASE_DIR, String(userId))
        if (!fs.existsSync(authFolder)) return res.status(404).json({ ok: false, error: 'Auth folder not found' })
        const files = fs.readdirSync(authFolder)
        let deleted = []
        for (const f of files) { if (f.startsWith('session-') || f.startsWith('sender-key-')) { try { fs.rmSync(path.join(authFolder, f)); deleted.push(f) } catch(e) {} } }
        console.log(`🧹 Clean ALL ${deleted.length} files for ${userId}`)
        try {
            const session = sessions[String(userId)]; if (session && session.sock) { try { session.sock.end(undefined) } catch(e) {} } delete sessions[String(userId)]; await new Promise(r => setTimeout(r, 2000)); await createSession(userId); await new Promise(r => setTimeout(r, 3000))
            try { const s = sessions[String(userId)]; if (s && s.sock) { const groups = await s.sock.groupFetchAllParticipating(); console.log(`✅ Auto-fetched ${Object.keys(groups).length} groups after clean-all`); s.groups = { ...s.groups, ...groups } } } catch(e) { console.log(`Auto fetch after clean-all failed: ${e.message}`) }
        } catch(e) { console.error(`Clean-all reconnect error: ${e}`) }
        res.json({ ok: true, deleted: deleted.length, files: deleted.slice(0,30), message: `Cleaned ALL ${deleted.length} files, reconnected` })
    } catch (e) { res.status(500).json({ ok: false, error: e.message }) }
})

app.post('/restore-appstate', async (req, res) => {
    const userId = req.body?.userId || req.query.userId || req.query.user_id
    if (!userId) return res.status(400).json({ ok: false, error: 'userId required' })
    try {
        const authFolder = path.join(AUTH_BASE_DIR, String(userId))
        const backupDir = path.join(BACKUP_BASE_DIR, String(userId), 'whatsapp_auth_backup', String(userId))
        if (!fs.existsSync(backupDir)) return res.status(404).json({ ok: false, error: 'Backup not found, need fresh QR' })
        if (!fs.existsSync(authFolder)) fs.mkdirSync(authFolder, { recursive: true })
        const backupFiles = fs.readdirSync(backupDir)
        let restored = []
        for (const f of backupFiles) { if (f.startsWith('app-state-sync-')) { try { fs.copyFileSync(path.join(backupDir, f), path.join(authFolder, f)); restored.push(f) } catch(e) {} } }
        console.log(`♻️ Restored ${restored.length} app-state files for ${userId}`)
        res.json({ ok: true, restored: restored.length, files: restored })
    } catch (e) { res.status(500).json({ ok: false, error: e.message }) }
})

// v7: Force sync group participants and build sessions - with LID support
app.post('/force-group-sync', async (req, res) => {
    const userId = req.body?.userId || req.query.userId || req.query.user_id
    const groupId = req.body?.groupId || req.query.groupId || '120363312386194255@g.us'
    if (!userId) return res.status(400).json({ ok: false, error: 'userId required' })
    let session = sessions[String(userId)]
    if (!session) return res.status(404).json({ ok: false, error: 'Session not found' })
    if (!session.isConnected) return res.status(503).json({ ok: false, error: 'Not connected' })
    try {
        console.log(`🔧 Force group sync for ${userId} group ${groupId} (LID support)`)
        let participants = []
        let meta = null
        try {
            meta = await session.sock.groupMetadata(groupId)
            participants = (meta.participants || []).map(p => p.id || p)
            console.log(`👥 Group ${groupId} has ${participants.length} participants: ${participants.slice(0,3).join(', ')}...`)
            session.groups[groupId] = meta
        } catch (e) { console.log(`groupMetadata failed: ${e.message}`) }

        let onWhatsAppResults = []
        let lidMappings = []
        for (const p of participants) {
            if (p === session.sock.user?.id) continue
            try {
                if (p.endsWith('@lid')) {
                    // Try to get PN for LID via lidMapping
                    try {
                        const pn = await session.sock.signalRepository?.lidMapping?.getPNForLID(p)
                        console.log(`   LID ${p} -> PN ${pn}`)
                        if (pn) {
                            lidMappings.push({ lid: p, pn })
                            const result = await session.sock.onWhatsApp(pn)
                            onWhatsAppResults.push({ jid: p, pn, exists: result?.[0]?.exists, type: 'lid->pn' })
                        } else {
                            onWhatsAppResults.push({ jid: p, error: 'No PN mapping found', type: 'lid' })
                        }
                    } catch (e) {
                        onWhatsAppResults.push({ jid: p, error: e.message, type: 'lid' })
                    }
                } else if (p.includes('@s.whatsapp.net')) {
                    const result = await session.sock.onWhatsApp(p)
                    onWhatsAppResults.push({ jid: p, exists: result?.[0]?.exists, type: 'pn' })
                }
                await new Promise(r => setTimeout(r, 300))
            } catch (e) { onWhatsAppResults.push({ jid: p, error: e.message }) }
        }

        await new Promise(r => setTimeout(r, 2000))

        const authFolder = path.join(AUTH_BASE_DIR, String(userId))
        const files = fs.existsSync(authFolder) ? fs.readdirSync(authFolder) : []
        const senderKeys = files.filter(f => f.startsWith('sender-key-') && f.includes(groupId.split('@')[0]))
        const sessionFiles = files.filter(f => f.startsWith('session-'))

        res.json({ ok: true, groupId, participants: participants.length, participantList: participants, onWhatsApp: onWhatsAppResults, lidMappings, senderKeys: senderKeys.length, senderKeyFiles: senderKeys, sessionFiles: sessionFiles.length, authFiles: files.length })
    } catch (e) { res.status(500).json({ ok: false, error: e.message, stack: e.stack?.slice(0,800) }) }
})

app.post('/send', async (req, res) => {
    const { to, text, imageBase64, userId, user_id } = req.body
    const finalUserId = userId || user_id
    let session = sessions[String(finalUserId)]
    
    if (Object.keys(sessions).length === 0) {
        console.log(`⚠️ No sessions in memory, trying restore...`)
        try { await restoreSessionsFromDisk(); await new Promise(r => setTimeout(r, 3000)); session = sessions[String(finalUserId)] } catch (e) {}
        if (Object.keys(sessions).length === 0) {
            const baseExists = fs.existsSync(AUTH_BASE_DIR)
            const folders = baseExists ? fs.readdirSync(AUTH_BASE_DIR) : []
            return res.status(500).json({ ok: false, error: `No sessions after restore - auth base exists=${baseExists} folders=${folders.length}`, code: 'NO_SESSIONS_IN_MEM' })
        }
    }
    
    if (!finalUserId || !session) {
        const authFolder = path.join(AUTH_BASE_DIR, String(finalUserId))
        if (fs.existsSync(authFolder)) {
            const files = fs.readdirSync(authFolder)
            if (files.length < 2) {
                console.log(`⚠️ Send: auth folder empty/corrupted for ${finalUserId} - deleting`)
                fullyDeleteSession(finalUserId, false)
                return res.status(404).json({ ok: false, error: `Session ${finalUserId} corrupted (empty auth) - deleted, need fresh QR`, code: 'EMPTY_AUTH_CORRUPTED', deleted: true })
            }
            try { session = await createSession(finalUserId); let attempts = 0; while (!session.isConnected && attempts < 40) { await new Promise(r => setTimeout(r, 500)); attempts++; } } catch (e) {}
        }
        if (!session) return res.status(404).json({ ok: false, error: `Session ${finalUserId} not found - need QR`, code: 'SESSION_NOT_FOUND' })
    }
    
    if (!session.isConnected) {
        let attempts = 0
        while (!session.isConnected && attempts < 20) { await new Promise(r => setTimeout(r, 500)); attempts++; }
        if (!session.isConnected) return res.status(503).json({ ok: false, error: `Not connected - scan QR`, code: 'NOT_CONNECTED', hasQR: !!session.qr, exists: true })
    }
    if (!to) return res.status(400).json({ ok: false, error: 'to required' })
    let finalTo = to
    if (to) {
        if (to.includes('@g.us') || to.includes('@s.whatsapp.net')) finalTo = to
        else if (/^\d+$/.test(to)) {
            if (to.startsWith('120363') || to.length > 15) finalTo = `${to}@g.us`
            else finalTo = `${to}@s.whatsapp.net`
        }
    }
    
    async function doSend() {
        const { mediaType } = req.body
        if (imageBase64) {
            const buffer = Buffer.from(imageBase64, 'base64')
            if (mediaType === 'video') return await session.sock.sendMessage(finalTo, { video: buffer, caption: text || '' })
            else if (mediaType === 'document') return await session.sock.sendMessage(finalTo, { document: buffer, mimetype: 'application/octet-stream', fileName: 'file', caption: text || '' })
            else return await session.sock.sendMessage(finalTo, { image: buffer, caption: text || '' })
        } else {
            return await session.sock.sendMessage(finalTo, { text: text || 'Hi' })
        }
    }

    try {
        await new Promise(r => setTimeout(r, 800))
        console.log(`📤 Attempting send to ${finalTo} via ${finalUserId} (groups cache: ${Object.keys(session.groups||{}).length})`)
        let result = await doSend()
        res.json({ ok: true, messageId: result.key.id, to: finalTo })
    } catch(e) {
        const errMsg = e.message || ''
        const errStack = e.stack || ''
        console.error(`❌ Send error to ${finalTo} via ${finalUserId}: ${errMsg}`)

        const isGroup = finalTo.endsWith('@g.us')
        const isNoSessions = errMsg.includes('No sessions') || errStack.includes('No sessions') || errMsg.includes('SessionError')

        if (isGroup && isNoSessions) {
            console.log(`🔄 Group No sessions for ${finalTo} - v7 advanced fix (auth has ${fs.existsSync(path.join(AUTH_BASE_DIR, String(finalUserId))) ? fs.readdirSync(path.join(AUTH_BASE_DIR, String(finalUserId))).length : 0} files)`)
            try {
                const authFolder = path.join(AUTH_BASE_DIR, String(finalUserId))
                if (fs.existsSync(authFolder)) {
                    const files = fs.readdirSync(authFolder)
                    const hasAppState = files.some(f => f.startsWith('app-state-sync-key-'))
                    if (!hasAppState) {
                        console.log(`⚠️ app-state-sync keys missing, restoring from backup...`)
                        const backupDir = path.join(BACKUP_BASE_DIR, String(finalUserId), 'whatsapp_auth_backup', String(finalUserId))
                        if (fs.existsSync(backupDir)) {
                            const backupFiles = fs.readdirSync(backupDir)
                            let restored = 0
                            for (const f of backupFiles) { if (f.startsWith('app-state-sync-')) { try { fs.copyFileSync(path.join(backupDir, f), path.join(authFolder, f)); restored++ } catch(e) {} } }
                            console.log(`♻️ Restored ${restored} app-state files`)
                        }
                    }
                }
            } catch(e) { console.log(`app-state restore check failed: ${e.message}`) }

            try {
                let participants = []
                try {
                    const groups = await session.sock.groupFetchAllParticipating()
                    console.log(`📋 Fetched ${Object.keys(groups).length} groups`)
                    session.groups = { ...session.groups, ...groups }
                    if (groups[finalTo]) {
                        const meta = groups[finalTo]
                        participants = (meta.participants || []).map(p => p.id || p)
                        console.log(`👥 Group ${finalTo} participants: ${participants.length}`)
                    }
                } catch (fetchErr) { console.log(`⚠️ groupFetch failed: ${fetchErr.message}`) }

                if (participants.length === 0) {
                    try {
                        const meta = await session.sock.groupMetadata(finalTo)
                        console.log(`📋 groupMetadata ${finalTo}: ${meta.subject} participants=${meta.participants?.length}`)
                        participants = (meta.participants || []).map(p => p.id || p)
                        session.groups[finalTo] = meta
                    } catch (metaErr) { console.log(`⚠️ groupMetadata failed: ${metaErr.message}`) }
                }

                if (participants.length > 0) {
                    console.log(`🔍 Ensuring sessions for ${participants.length} participants via onWhatsApp...`)
                    for (const p of participants) {
                        if (!p.includes('@s.whatsapp.net')) continue
                        if (p === session.sock.user?.id) continue
                        try { await session.sock.onWhatsApp(p); await new Promise(r => setTimeout(r, 250)) } catch(e2) {}
                    }
                }

                await new Promise(r => setTimeout(r, 3000))
                console.log(`🔄 Retrying send to ${finalTo} after participant sync...`)
                const retryResult = await doSend()
                console.log(`✅ Retry succeeded for ${finalTo}`)
                return res.json({ ok: true, messageId: retryResult.key.id, to: finalTo, retried: true, participants: participants.length })
            } catch (retryErr) {
                console.error(`❌ Retry failed for ${finalTo}: ${retryErr.message}`)
                try {
                    console.log(`🧹 Cleaning sender-key files and retry...`)
                    const authFolder = path.join(AUTH_BASE_DIR, String(finalUserId))
                    if (fs.existsSync(authFolder)) {
                        const files = fs.readdirSync(authFolder)
                        let cleaned = 0
                        for (const f of files) { if (f.startsWith('sender-key-')) { try { fs.rmSync(path.join(authFolder, f)); cleaned++ } catch(e) {} } }
                        console.log(`🧹 Cleaned ${cleaned} sender-key files`)
                        if (cleaned > 0) {
                            await new Promise(r => setTimeout(r, 3000))
                            try {
                                const retry3 = await doSend()
                                console.log(`✅ Retry3 after cleaning sender-keys succeeded`)
                                return res.json({ ok: true, messageId: retry3.key.id, to: finalTo, retried: true, cleaned })
                            } catch(e3) { console.log(`Retry3 failed: ${e3.message}`) }
                        }
                    }
                } catch (cleanErr) { console.error(`Clean retry failed: ${cleanErr.message}`) }

                return res.status(500).json({ 
                    ok: false, 
                    error: `No sessions for group ${finalTo} - needs more group messages to build sessions. This is normal for new linked devices.`, 
                    to: finalTo, 
                    code: 'NO_SESSIONS_GROUP_NEEDS_MESSAGE',
                    authFiles: fs.existsSync(path.join(AUTH_BASE_DIR, String(finalUserId))) ? fs.readdirSync(path.join(AUTH_BASE_DIR, String(finalUserId))).length : 0,
                    groupsCached: Object.keys(session.groups||{}).length,
                    stack: retryErr.stack?.slice(0,800),
                    fix_steps: [
                        `1. From MAIN phone, send 3-4 messages in group ${finalTo}`,
                        `2. Ask 3-4 members to send messages (important - builds sessions for each)`,
                        `3. Wait 15s`,
                        `4. POST /force-group-sync?userId=${finalUserId}&groupId=${finalTo}`,
                        `5. POST /clean-all-sessions?userId=${finalUserId}`,
                        `6. Wait 5s, retry send`
                    ],
                    fix: `curl -X POST http://localhost:3001/force-group-sync?userId=${finalUserId}&groupId=${finalTo} && curl -X POST http://localhost:3001/clean-all-sessions?userId=${finalUserId}`
                })
            }
        }

        if (isNoSessions) {
            console.log(`🔥 No sessions for ${finalUserId} - checking corruption`)
            try {
                const authFolder = path.join(AUTH_BASE_DIR, String(finalUserId))
                if (fs.existsSync(authFolder)) {
                    const files = fs.readdirSync(authFolder)
                    if (files.length < 3) {
                        console.log(`🔥 Auth corrupted (<3 files), deleting`)
                        fullyDeleteSession(finalUserId, true)
                        return res.status(500).json({ ok: false, error: 'No sessions - auth corrupted, deleted, need fresh QR', to: finalTo, code: 'NO_SESSIONS_CORRUPTED_DELETED', deleted: true, authFiles: files.length })
                    }
                }
            } catch (delErr) { console.error(`Failed to auto-delete: ${delErr}`) }
            return res.status(500).json({ ok: false, error: `No sessions for ${finalTo}. For groups, need group messages to build sessions.`, to: finalTo, code: 'NO_SESSIONS_CORRUPTED', stack: errStack.slice(0,500) })
        }

        res.status(500).json({ ok: false, error: e.message, to: finalTo, stack: e.stack?.slice(0,500), code: 'SEND_FAILED' })
    }
})

app.listen(PORT, '0.0.0.0', async () => {
    console.log(`🚀 WhatsApp FIXED v7 baileys7 on 0.0.0.0:${PORT} - fixes 401,428, group No sessions with participant sync`)
    console.log(`📁 Auth base: ${AUTH_BASE_DIR}`)
    setTimeout(() => { try { restoreSessionsFromDisk() } catch(e) { console.error(`Restore startup error: ${e}`) } }, 2000)
    setInterval(async () => {
        try {
            if (Object.keys(sessions).length === 0 && fs.existsSync(AUTH_BASE_DIR)) {
                const folders = fs.readdirSync(AUTH_BASE_DIR)
                if (folders.length > 0) {
                    console.log(`⏰ Periodic restore check: ${folders.length} folders on disk, restoring...`)
                    await restoreSessionsFromDisk()
                }
            }
        } catch(e) { console.error(`Periodic restore error: ${e}`) }
    }, 60000)
})
