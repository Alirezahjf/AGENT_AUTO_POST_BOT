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
const AUTH_BASE_DIR = path.join(__dirname, 'auth')
const SESSIONS_DB_FILE = path.join(__dirname, 'sessions_db.json')
const BACKUP_BASE_DIR = path.join(__dirname, '..', 'all_pg_agnet', 'AGENT-MANAGER_BOTS_MASSENGER', 'users')

// ========== Persistent Session DB ==========

function loadSessionsDB() {
    try {
        if (fs.existsSync(SESSIONS_DB_FILE)) {
            const data = JSON.parse(fs.readFileSync(SESSIONS_DB_FILE, 'utf-8'))
            console.log(`📂 Loaded sessions DB: ${Object.keys(data).length} entries`)
            return data
        }
    } catch (e) {
        console.error(`❌ Failed to load sessions DB: ${e}`)
    }
    return {}
}

function saveSessionsDB(db) {
    try {
        fs.writeFileSync(SESSIONS_DB_FILE, JSON.stringify(db, null, 2), 'utf-8')
    } catch (e) {
        console.error(`❌ Failed to save sessions DB: ${e}`)
    }
}

function updateSessionInDB(userId, info) {
    try {
        const db = loadSessionsDB()
        db[String(userId)] = {
            ...db[String(userId)],
            ...info,
            userId: String(userId),
            lastUpdate: new Date().toISOString(),
            authPath: path.join(AUTH_BASE_DIR, String(userId)),
            authExists: fs.existsSync(path.join(AUTH_BASE_DIR, String(userId))),
            authFiles: fs.existsSync(path.join(AUTH_BASE_DIR, String(userId))) ? fs.readdirSync(path.join(AUTH_BASE_DIR, String(userId))).length : 0
        }
        saveSessionsDB(db)
        try {
            if (fs.existsSync(BACKUP_BASE_DIR)) {
                const userBackupInfoFile = path.join(BACKUP_BASE_DIR, String(userId), 'whatsapp_session_info.json')
                fs.mkdirSync(path.dirname(userBackupInfoFile), { recursive: true })
                fs.writeFileSync(userBackupInfoFile, JSON.stringify(db[String(userId)], null, 2), 'utf-8')
            }
        } catch (e) {}
    } catch (e) {
        console.error(`❌ updateSessionInDB error: ${e}`)
    }
}

function deleteSessionFromDB(userId) {
    try {
        const db = loadSessionsDB()
        if (db[String(userId)]) {
            delete db[String(userId)]
            saveSessionsDB(db)
            console.log(`🗑️ Deleted ${userId} from sessions DB`)
        }
    } catch (e) {
        console.error(`❌ deleteSessionFromDB error: ${e}`)
    }
}

function backupAuthFolder(userId) {
    try {
        const authFolder = path.join(AUTH_BASE_DIR, String(userId))
        if (!fs.existsSync(authFolder)) return
        if (fs.existsSync(BACKUP_BASE_DIR)) {
            const backupDir = path.join(BACKUP_BASE_DIR, String(userId), 'whatsapp_auth_backup', String(userId))
            fs.mkdirSync(backupDir, { recursive: true })
            const files = fs.readdirSync(authFolder)
            for (const file of files) {
                try {
                    const src = path.join(authFolder, file)
                    const dest = path.join(backupDir, file)
                    if (fs.statSync(src).isFile()) fs.copyFileSync(src, dest)
                } catch (e) {}
            }
            console.log(`💾 Backed up ${files.length} auth files for ${userId}`)
        }
    } catch (e) {
        console.error(`❌ backupAuthFolder error for ${userId}: ${e}`)
    }
}

function restoreFromUserBackup(userId) {
    try {
        const backupDir = path.join(BACKUP_BASE_DIR, String(userId), 'whatsapp_auth_backup', String(userId))
        const authFolder = path.join(AUTH_BASE_DIR, String(userId))
        if (fs.existsSync(backupDir) && !fs.existsSync(authFolder)) {
            console.log(`♻️ Restoring auth from user backup: ${backupDir} -> ${authFolder}`)
            fs.mkdirSync(authFolder, { recursive: true })
            const files = fs.readdirSync(backupDir)
            for (const file of files) {
                try { fs.copyFileSync(path.join(backupDir, file), path.join(authFolder, file)) } catch (e) {}
            }
            console.log(`✅ Restored ${files.length} files from user backup for ${userId}`)
            return true
        }
    } catch (e) {
        console.error(`❌ restoreFromUserBackup error for ${userId}: ${e}`)
    }
    return false
}

// ✅ NEW: Fully delete corrupted session - fixes "No sessions" + "session already exists"
function fullyDeleteSession(userId) {
    const userIdStr = String(userId)
    console.log(`🗑️ Fully deleting session ${userIdStr} - for force reset / No sessions fix`)
    try {
        const session = sessions[userIdStr]
        if (session && session.sock) {
            try { session.sock.end() } catch(e) {}
            try { session.sock.logout() } catch(e) {}
        }
    } catch(e) {}
    try {
        delete sessions[userIdStr]
    } catch(e) {}
    try {
        const authFolder = path.join(AUTH_BASE_DIR, userIdStr)
        if (fs.existsSync(authFolder)) {
            fs.rmSync(authFolder, { recursive: true, force: true })
            console.log(`🗑️ Deleted auth folder ${authFolder}`)
        }
    } catch(e) {
        console.error(`❌ Failed to delete auth folder for ${userIdStr}: ${e}`)
    }
    try {
        deleteSessionFromDB(userIdStr)
    } catch(e) {}
    // Don't delete backup - keep for manual recovery if needed
    console.log(`✅ Fully deleted session ${userIdStr} - ready for fresh QR`)
}

async function restoreSessionsFromDisk() {
    try {
        const authDir = AUTH_BASE_DIR
        if (!fs.existsSync(authDir)) {
            fs.mkdirSync(authDir, { recursive: true })
        }
        const db = loadSessionsDB()
        console.log(`📂 Sessions DB has ${Object.keys(db).length} entries: ${Object.keys(db).join(', ')}`)
        for (const userId of Object.keys(db)) {
            const authPath = path.join(authDir, userId)
            if (!fs.existsSync(authPath)) {
                console.log(`⚠️ Auth folder missing for ${userId} from DB, trying user backup...`)
                restoreFromUserBackup(userId)
            }
        }
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
                        for (const file of files) {
                            try { fs.copyFileSync(path.join(backupAuthPath, file), path.join(mainAuthPath, file)) } catch(e) {}
                        }
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
                    if (files.length > 0) {
                        console.log(`♻️ Restoring session for ${userId} (${files.length} files)`)
                        await createSession(userId)
                        await new Promise(r => setTimeout(r, 3000))
                    } else {
                        console.log(`⚠️ Empty auth folder for ${userId}, deleting to allow fresh login`)
                        // ✅ FIX: Empty folder = corrupted, delete it
                        fullyDeleteSession(userId)
                    }
                }
            } catch (e) {
                console.error(`❌ Failed to restore ${userId}: ${e.message}`)
            }
        }
        console.log(`✅ Restore done, ${Object.keys(sessions).length} sessions in memory`)
        for (const userId of Object.keys(sessions)) {
            updateSessionInDB(userId, { connected: sessions[userId].isConnected, restoredAt: new Date().toISOString() })
        }
    } catch (e) {
        console.error(`❌ restoreSessionsFromDisk error: ${e} ${e.stack}`)
    }
}

async function createSession(userId, phoneNumber = null, force = false) {
    const userIdStr = String(userId)
    console.log(`🔧 Creating session for ${userIdStr} phone=${phoneNumber} force=${force} authBase=${AUTH_BASE_DIR}`)

    // ✅ FIX: If force=true, fully delete old session first - solves "session already exists" error
    if (force) {
        console.log(`🔥 Force flag - fully deleting old session ${userIdStr} before creating new`)
        fullyDeleteSession(userIdStr)
        // Wait a bit
        await new Promise(r => setTimeout(r, 500))
    }

    if (sessions[userIdStr] && sessions[userIdStr].isConnected && !force) {
        console.log(`♻️ Session ${userIdStr} already connected, returning existing (use force=true to recreate)`)
        updateSessionInDB(userIdStr, { connected: true, phoneNumber, lastCreate: new Date().toISOString() })
        return sessions[userIdStr]
    }
    if (sessions[userIdStr] && sessions[userIdStr].sock) { 
        try { 
            console.log(`🔄 Closing existing sock for ${userIdStr}`)
            sessions[userIdStr].sock.end() 
        } catch(e) {} 
    }
    
    const authFolderCheck = path.join(AUTH_BASE_DIR, userIdStr)
    if (!fs.existsSync(authFolderCheck)) {
        restoreFromUserBackup(userIdStr)
    }
    
    const authFolder = path.join(AUTH_BASE_DIR, userIdStr)
    updateSessionInDB(userIdStr, { phoneNumber, authPath: authFolder, creating: true })
    if (!fs.existsSync(authFolder)) fs.mkdirSync(authFolder, { recursive: true })
    const { state, saveCreds } = await useMultiFileAuthState(authFolder)
    const { version } = await fetchLatestBaileysVersion()
    console.log(`📦 Baileys version ${version} for ${userIdStr}`)
    const sock = makeWASocket({ version, auth: state, logger, printQRInTerminal: false, browser: ['AGENT_AUTO_POST_BOT', 'Chrome', '1.0.0'] })
    const session = { sock, isConnected: false, qr: null, qrImage: null, pairingCode: null, phoneNumber, lastUpdate: new Date(), userId: userIdStr, lastQR: null, groups: {}, groupsCacheTime: null, lastGroupsFetch: null, forceReset: force }
    sessions[userIdStr] = session
    sock.ev.on('creds.update', saveCreds)
    try {
        sock.ev.on('groups.upsert', (groups) => {
            try {
                console.log(`📋 groups.upsert for ${userIdStr}: ${groups.length} groups`)
                for (const g of groups) {
                    if (g.id) session.groups[g.id] = g
                }
                session.groupsCacheTime = new Date()
            } catch(e) {}
        })
        sock.ev.on('groups.update', (updates) => {
            try {
                for (const u of updates) {
                    if (u.id && session.groups[u.id]) {
                        session.groups[u.id] = { ...session.groups[u.id], ...u }
                    }
                }
            } catch(e) {}
        })
        sock.ev.on('chats.upsert', (chats) => {
            try {
                for (const c of chats) {
                    if (c.id && c.id.endsWith('@g.us')) {
                        if (!session.groups[c.id]) {
                            session.groups[c.id] = { id: c.id, subject: c.name || c.id, participants: [] }
                        }
                    }
                }
            } catch(e) {}
        })
    } catch(e) {}
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
            } catch(e) {}
        }
        if (connection === 'close') {
            const statusCode = lastDisconnect?.error?.output?.statusCode
            const reason = lastDisconnect?.error?.message || 'unknown'
            console.log(`❌ Closed for ${userIdStr} code=${statusCode} reason=${reason}`)
            session.isConnected = false
            // ✅ FIX: If loggedOut and forceReset, delete auth folder to allow fresh login
            if (statusCode === DisconnectReason.loggedOut) {
                if (session.forceReset) {
                    console.log(`🚫 Logged out + forceReset for ${userIdStr} - deleting auth folder for fresh login`)
                    try { fs.rmSync(authFolder, { recursive: true, force: true }) } catch(e) {}
                    delete sessions[userIdStr]
                    deleteSessionFromDB(userIdStr)
                } else {
                    console.log(`🚫 Logged out ${userIdStr} - keeping auth folder, will retry in 10s (call DELETE /session?userId=${userIdStr}&force=true for fresh)`)
                    setTimeout(() => createSession(userIdStr, phoneNumber), 10000)
                }
            } else {
                console.log(`🔄 Reconnect ${userIdStr} in 5s... code=${statusCode}`)
                setTimeout(() => createSession(userIdStr, phoneNumber), 5000)
            }
        } else if (connection === 'open') {
            console.log(`✅✅✅ CONNECTED for ${userIdStr}! ✅✅✅`)
            session.isConnected = true
            session.qr = null
            session.qrImage = null
            session.pairingCode = null
            session.forceReset = false
            updateSessionInDB(userIdStr, { 
                connected: true, 
                phoneNumber, 
                connectedAt: new Date().toISOString(),
                lastConnected: new Date().toISOString()
            })
            setTimeout(() => backupAuthFolder(userIdStr), 2000)
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
    const list = Object.keys(sessions).map(uid => ({ userId: uid, connected: sessions[uid].isConnected, hasQR: !!sessions[uid].qr, hasCode: !!sessions[uid].pairingCode, phone: sessions[uid].phoneNumber }))
    res.json({ status: 'ok', service: 'whatsapp-fixed-v2', uptime: process.uptime(), sessionsCount: list.length, sessions: list })
})

app.get('/qr', async (req, res) => {
    const userId = req.query.userId || req.query.user_id
    const phone = req.query.phone || null
    const ownPhone = req.query.ownPhone || req.query.own_phone || phone || null
    const force = req.query.force === 'true' || req.query.force === '1'  // ✅ NEW: force param
    if (!userId) return res.status(400).json({ ok: false, error: 'userId required' })
    try {
        let session = sessions[String(userId)]
        if (force) {
            console.log(`🔥 /qr force=true for ${userId} - deleting old session`)
            fullyDeleteSession(userId)
            session = null
        }
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

        if (session.isConnected && !force) {
            return res.json({ ok: true, connected: true, userId: String(userId), phoneNumber: session.phoneNumber })
        }

        const phoneForCode = ownPhone || phone || session.phoneNumber
        if (phoneForCode && !session.pairingCode) {
            try {
                const code = await getPairingCodeWithRetry(session.sock, phoneForCode, 2)
                if (code) {
                    session.pairingCode = code
                    updateSessionInDB(String(userId), { pairingCode: code, phoneForCode })
                }
            } catch (e) {}
        }

        if (session.qr) {
            return res.json({ 
                ok: true, 
                connected: false, 
                hasQR: true, 
                qr: session.qr, 
                qrImage: session.qrImage,
                pairingCode: session.pairingCode,
                pairingCodePlain: session.pairingCode ? session.pairingCode.replace('-', '') : null,
                pairingCodeFormatted: session.pairingCode,
                userId: String(userId),
                phoneNumber: session.phoneNumber,
                phoneForPairing: phoneForCode,
                instructions: 'Scan QR or enter pairing code',
                copyableCode: session.pairingCode,
                howTo: {
                    qr: 'WhatsApp -> Settings -> Linked Devices -> Link a Device -> Scan QR',
                    code: `WhatsApp -> Settings -> Linked Devices -> Link with phone number -> Enter code: ${session.pairingCode}`,
                }
            })
        }

        return res.json({ ok: false, connected: false, hasQR: false, error: 'QR not ready, try again in 2s', userId: String(userId), pairingCode: session.pairingCode })
    } catch (e) {
        console.error(`QR error: ${e} ${e.stack}`)
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
    if (!userId) return res.json({ ok: true, count: Object.keys(sessions).length, sessions: Object.keys(sessions).map(uid => ({ userId: uid, connected: sessions[uid].isConnected, hasQR: !!sessions[uid].qr, hasCode: !!sessions[uid].pairingCode, pairingCode: sessions[uid].pairingCode })), authBase: AUTH_BASE_DIR, authExists: fs.existsSync(AUTH_BASE_DIR), authFolders: fs.existsSync(AUTH_BASE_DIR) ? fs.readdirSync(AUTH_BASE_DIR) : [] })
    let session = sessions[String(userId)]
    if (!session) {
        const authFolder = path.join(AUTH_BASE_DIR, String(userId))
        if (fs.existsSync(authFolder)) {
            const files = fs.readdirSync(authFolder)
            // ✅ FIX: If auth folder empty (user manually deleted files), treat as not exists
            if (files.length === 0) {
                console.log(`⚠️ Auth folder empty for ${userId} at ${authFolder} - deleting to allow fresh login`)
                fullyDeleteSession(userId)
                return res.json({ ok: false, connected: false, exists: false, empty: true, userId: String(userId), message: 'Auth folder empty - deleted, ready for fresh QR. Call /qr?force=true' })
            }
            console.log(`♻️ Status check: ${userId} not in memory but auth exists (${files.length} files), restoring...`)
            try {
                session = await createSession(String(userId))
                let attempts = 0
                while (!session.isConnected && !session.qr && attempts < 10) {
                    await new Promise(r => setTimeout(r, 500))
                    attempts++
                }
            } catch (e) {
                console.error(`❌ Restore failed for status ${userId}: ${e} ${e.stack}`)
            }
        }
    }
    if (!session) return res.json({ ok: false, connected: false, exists: false, userId: String(userId), authExists: fs.existsSync(path.join(AUTH_BASE_DIR, String(userId))) })
    res.json({ ok: true, connected: session.isConnected, exists: true, hasQR: !!session.qr, hasCode: !!session.pairingCode, pairingCode: session.pairingCode, phone: session.phoneNumber, userId: String(userId) })
})

app.get('/chats', async (req, res) => {
    const userId = req.query.userId || req.query.user_id
    if (!userId) return res.status(400).json({ ok: false, error: 'userId required' })
    let session = sessions[String(userId)]
    if (!session) {
        const authFolder = path.join(AUTH_BASE_DIR, String(userId))
        if (fs.existsSync(authFolder)) {
            try {
                session = await createSession(String(userId))
                let attempts = 0
                while (!session.isConnected && attempts < 20) {
                    await new Promise(r => setTimeout(r, 500))
                    attempts++
                }
            } catch (e) {}
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
                if (count > 0) {
                    session.groups = { ...session.groups, ...groups }
                    session.lastGroupsFetch = new Date()
                    break
                }
                if (Object.keys(session.groups||{}).length > 0) {
                    groups = session.groups
                    fetchedVia = 'cache_during_fetch'
                    break
                }
                if (attempt < 10) await new Promise(r => setTimeout(r, 3000))
            } catch (e) {
                lastError = e
                if (attempt < 10) await new Promise(r => setTimeout(r, 2000))
            }
        }
        if (Object.keys(groups).length === 0 && session.groups && Object.keys(session.groups).length > 0) {
            groups = session.groups
            fetchedVia = 'cache_after_fetch'
        }
        try {
            for (const [id, group] of Object.entries(groups)) {
                chats.push({ id: id, name: group.subject || group.name || id, type: 'group', participants: group.participants?.length || group.participantsCount || 0, isGroup: true })
            }
        } catch (e) {}
        res.json({ 
            ok: true, 
            connected: true,
            chats: chats,
            count: chats.length,
            userId: String(userId),
            message: chats.length > 0 ? `Found ${chats.length} groups` : 'No groups found - wait 60s and try again or send group ID manually: 120363312386194255@g.us',
            debug: { lastError: lastError?.message || null, fetchedVia, cacheSize: Object.keys(session.groups||{}).length }
        })
    } catch (e) {
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
    const phone = req.query.phone || req.query.ownPhone || req.query.own_phone
    if (!userId || !phone) return res.status(400).json({ ok: false, error: 'userId and phone required' })
    let session = sessions[String(userId)]
    if (!session) {
        try {
            session = await createSession(String(userId), phone)
            let attempts = 0
            while (!session.sock && attempts < 10) { await new Promise(r => setTimeout(r, 500)); attempts++ }
        } catch (e) {
            return res.status(500).json({ ok: false, error: `Failed to create session: ${e.message}` })
        }
    }
    try {
        const code = await getPairingCodeWithRetry(session.sock, phone, 3)
        if (code) {
            session.pairingCode = code
            session.phoneNumber = phone
            updateSessionInDB(String(userId), { pairingCode: code, phoneNumber: phone })
            return res.json({ ok: true, pairingCode: code, pairingCodePlain: code.replace('-', ''), userId: String(userId), phone })
        } else {
            return res.status(500).json({ ok: false, error: `Failed to get pairing code for ${phone}` })
        }
    } catch (e) {
        res.status(500).json({ ok: false, error: e.message })
    }
})

app.get('/pairing-code-text', async (req, res) => {
    const userId = req.query.userId || req.query.user_id
    const session = sessions[String(userId)]
    if (!session || !session.pairingCode) return res.status(404).send('No pairing code')
    res.set('Content-Type', 'text/plain; charset=utf-8')
    res.send(session.pairingCode)
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

// ✅ FIXED: DELETE now supports force=true and cleans DB + handles No sessions
app.delete('/session', async (req, res) => {
    const userId = req.query.userId || req.query.user_id || req.body?.userId
    const force = req.query.force === 'true' || req.query.force === '1' || req.body?.force === true
    if (!userId) return res.status(400).json({ ok: false, error: 'userId required' })
    console.log(`🗑️ DELETE /session for ${userId} force=${force}`)
    try {
        fullyDeleteSession(userId)
        res.json({ ok: true, deleted: true, userId: String(userId), force, message: 'Session fully deleted - ready for fresh QR. Call /qr?force=true' })
    } catch (e) {
        res.status(500).json({ ok: false, error: e.message })
    }
})

// ✅ NEW: Force reset endpoint - solves "session already exists" error
app.post('/reset', async (req, res) => {
    const userId = req.body?.userId || req.query.userId || req.query.user_id
    const phone = req.body?.phone || req.query.phone
    if (!userId) return res.status(400).json({ ok: false, error: 'userId required' })
    console.log(`🔥 POST /reset for ${userId} phone=${phone} - force fresh QR`)
    try {
        fullyDeleteSession(userId)
        await new Promise(r => setTimeout(r, 1000))
        const session = await createSession(userId, phone, true)
        let attempts = 0
        while (!session.qr && !session.isConnected && attempts < 40) { await new Promise(r => setTimeout(r, 500)); attempts++ }
        if (session.qr) {
            return res.json({ ok: true, reset: true, hasQR: true, qr: session.qr, qrImage: session.qrImage, pairingCode: session.pairingCode, userId: String(userId), message: 'Old session deleted, new QR ready - scan now' })
        }
        return res.json({ ok: true, reset: true, connected: session.isConnected, userId: String(userId), hasQR: !!session.qr })
    } catch (e) {
        console.error(`Reset error: ${e}`)
        res.status(500).json({ ok: false, error: e.message })
    }
})

app.get('/restore', async (req, res) => {
    const userId = req.query.userId || req.query.user_id
    if (userId) {
        const authFolder = path.join(AUTH_BASE_DIR, String(userId))
        if (fs.existsSync(authFolder)) {
            const files = fs.readdirSync(authFolder)
            if (files.length === 0) {
                fullyDeleteSession(userId)
                return res.status(404).json({ ok: false, error: 'Auth folder empty - deleted, ready for fresh QR', empty: true, code: 'EMPTY_AUTH' })
            }
            try {
                const session = await createSession(String(userId))
                let attempts = 0
                while (!session.isConnected && attempts < 20) { await new Promise(r => setTimeout(r, 500)); attempts++ }
                return res.json({ ok: true, restored: true, connected: session.isConnected, userId: String(userId), files: files.length })
            } catch (e) {
                return res.status(500).json({ ok: false, error: e.message })
            }
        } else {
            return res.status(404).json({ ok: false, error: `Auth folder not found`, code: 'NOT_FOUND' })
        }
    } else {
        await restoreSessionsFromDisk()
        return res.json({ ok: true, sessions: Object.keys(sessions).length, list: Object.keys(sessions).map(uid => ({ userId: uid, connected: sessions[uid].isConnected })) })
    }
})

app.post('/send', async (req, res) => {
    const { to, text, imageBase64, userId, user_id } = req.body
    const finalUserId = userId || user_id
    let session = sessions[String(finalUserId)]
    
    if (Object.keys(sessions).length === 0) {
        console.log(`⚠️ No sessions in memory, trying restore...`)
        try {
            await restoreSessionsFromDisk()
            await new Promise(r => setTimeout(r, 3000))
            session = sessions[String(finalUserId)]
        } catch (e) {}
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
            if (files.length === 0) {
                console.log(`⚠️ Send: auth folder empty for ${finalUserId} - corrupted, deleting`)
                fullyDeleteSession(finalUserId)
                return res.status(404).json({ ok: false, error: `Session ${finalUserId} corrupted (empty auth) - deleted, need fresh QR`, code: 'EMPTY_AUTH_CORRUPTED', deleted: true })
            }
            try {
                session = await createSession(finalUserId)
                let attempts = 0
                while (!session.isConnected && attempts < 40) { await new Promise(r => setTimeout(r, 500)); attempts++; }
            } catch (e) {}
        }
        if (!session) {
            return res.status(404).json({ ok: false, error: `Session ${finalUserId} not found - need QR`, code: 'SESSION_NOT_FOUND' })
        }
    }
    
    if (!session.isConnected) {
        let attempts = 0
        while (!session.isConnected && attempts < 20) { await new Promise(r => setTimeout(r, 500)); attempts++; }
        if (!session.isConnected) {
            return res.status(503).json({ ok: false, error: `Not connected - scan QR`, code: 'NOT_CONNECTED', hasQR: !!session.qr, exists: true })
        }
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
    
    try {
        await new Promise(r => setTimeout(r, 500))
        let result
        const { mediaType } = req.body
        console.log(`📤 Attempting send to ${finalTo} via ${finalUserId}`)
        if (imageBase64) {
            const buffer = Buffer.from(imageBase64, 'base64')
            if (mediaType === 'video') result = await session.sock.sendMessage(finalTo, { video: buffer, caption: text || '' })
            else if (mediaType === 'document') result = await session.sock.sendMessage(finalTo, { document: buffer, mimetype: 'application/octet-stream', fileName: 'file', caption: text || '' })
            else result = await session.sock.sendMessage(finalTo, { image: buffer, caption: text || '' })
        } else {
            result = await session.sock.sendMessage(finalTo, { text: text || 'Hi' })
        }
        res.json({ ok: true, messageId: result.key.id, to: finalTo })
    } catch(e) {
        const errMsg = e.message || ''
        const errStack = e.stack || ''
        console.error(`❌ Send error to ${finalTo} via ${finalUserId}: ${errMsg}`)

        // ✅ FIX: Detect "No sessions" - corrupted signal keys - auto delete and require fresh QR
        if (errMsg.includes('No sessions') || errStack.includes('No sessions') || errMsg.includes('SessionError')) {
            console.log(`🔥 No sessions detected for ${finalUserId} - signal keys corrupted! Deleting session for fresh login`)
            // Don't auto-delete immediately, but mark as corrupted and suggest reset
            // Actually delete to allow fresh QR on next /qr?force=true
            try {
                // Keep auth folder for debug but delete session from memory to force recreate?
                // Better: fully delete so next QR works
                // But let's first try to keep creds.json and delete only app-state?
                // For safety, fully delete and tell user to rescan
                const authFolder = path.join(AUTH_BASE_DIR, String(finalUserId))
                // Check if auth folder has only few files (corrupted)
                if (fs.existsSync(authFolder)) {
                    const files = fs.readdirSync(authFolder)
                    console.log(`📂 Auth folder for ${finalUserId} has ${files.length} files: ${files.join(', ')} - might be corrupted`)
                    // If creds.json exists but signal keys missing, Baileys will throw No sessions
                    // Solution: delete and require fresh QR
                    if (files.length < 3) {
                        console.log(`🔥 Auth folder seems corrupted (<3 files), fully deleting for ${finalUserId}`)
                        fullyDeleteSession(finalUserId)
                        return res.status(500).json({ 
                            ok: false, 
                            error: 'No sessions - auth corrupted (empty or <3 files), session deleted, need fresh QR. Call /qr?force=true or /reset', 
                            to: finalTo, 
                            code: 'NO_SESSIONS_CORRUPTED_DELETED',
                            deleted: true,
                            authFiles: files.length,
                            sessionsKeys: Object.keys(sessions)
                        })
                    }
                }
            } catch (delErr) {
                console.error(`Failed to auto-delete corrupted session: ${delErr}`)
            }
            return res.status(500).json({ 
                ok: false, 
                error: `No sessions - signal keys missing for ${finalTo}. Session corrupted, need to reset: DELETE /session?userId=${finalUserId}&force=true then /qr?force=true`, 
                to: finalTo, 
                code: 'NO_SESSIONS_CORRUPTED',
                stack: errStack.slice(0,500),
                sessionsKeys: Object.keys(sessions),
                connected: session?.isConnected,
                suggestion: `curl -X DELETE http://localhost:3001/session?userId=${finalUserId}&force=true && curl http://localhost:3001/qr?userId=${finalUserId}&force=true&phone=YOUR_OWN_NUMBER`
            })
        }

        res.status(500).json({ ok: false, error: e.message, to: finalTo, stack: e.stack?.slice(0,500), code: 'SEND_FAILED' })
    }
})

app.listen(PORT, '0.0.0.0', async () => {
    console.log(`🚀 WhatsApp FIXED v2 on 0.0.0.0:${PORT} - handles No sessions + force reset`)
    console.log(`📁 Auth base: ${AUTH_BASE_DIR}`)
    setTimeout(() => restoreSessionsFromDisk(), 2000)
    setInterval(async () => {
        if (Object.keys(sessions).length === 0 && fs.existsSync(AUTH_BASE_DIR)) {
            const folders = fs.readdirSync(AUTH_BASE_DIR)
            if (folders.length > 0) {
                console.log(`⏰ Periodic restore check: ${folders.length} folders on disk, restoring...`)
                await restoreSessionsFromDisk()
            }
        }
    }, 60000)
})
