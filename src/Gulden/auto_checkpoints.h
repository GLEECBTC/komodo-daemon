// Copyright (c) 2009-2012 The Bitcoin developers
// Copyright (c) 2011-2013 The PPCoin developers
// Distributed under the MIT/X11 software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

/******************************************************************************
 * Copyright © 2025 The SuperNET Developers.                                  *
 *                                                                            *
 * See the AUTHORS, DEVELOPER-AGREEMENT and LICENSE files at                  *
 * the top-level directory of this distribution for the individual copyright  *
 * holder information and the developer policies on copyright and licensing.  *
 *                                                                            *
 * Unless otherwise agreed in a custom licensing agreement, no part of the    *
 * SuperNET software, including this file may be copied, modified, propagated *
 * or distributed except according to the terms contained in the LICENSE file *
 *                                                                            *
 * Removal or modification of this copyright notice is prohibited.            *
 *                                                                            *
 ******************************************************************************/

#ifndef GULDEN_AUTO_CHECKPOINT_H
#define  GULDEN_AUTO_CHECKPOINT_H

#include <map>
#include <vector>
#include <string>
#include "core_io.h"
#include "key.h"
#include "net.h"
#include "util.h"
#include "txdb.h"
#include "fs.h"
#include "streams.h"

class uint256;
class CBlockIndex;
class CSyncChkptMessage;

// Komodo added
namespace Checkpoints
{
    // Asset or KMD chain sync checkpoint activation params
    struct CSyncChkParams {
        int64_t activeAt = -1;
        std::string masterPubKey;
        
        CSyncChkParams() = default;
        CSyncChkParams(int64_t at, const std::string& key) : activeAt(at), masterPubKey(key) {}
    };
	extern bool fTryInitDone;

	struct CSyncCheckpoint {
        uint256 hash;

		ADD_SERIALIZE_METHODS;
		template <typename Stream, typename Operation>
		inline void SerializationOp(Stream& s, Operation ser_action)
		{
			READWRITE(hash);
		}

		CSyncCheckpoint() : hash(uint256()) {}
		CSyncCheckpoint(uint256 hashIn) : hash(hashIn) {}
		bool IsNull() { return hash.IsNull(); }
		uint256 GetHash() { return hash; }
		std::string ToString() const {
			std::ostringstream ss;
			ss << hash.ToString();
			return ss.str();
		} 
    };
}

namespace Checkpoints
{
	extern CSyncCheckpoint syncCheckpoint;
	extern CSyncCheckpoint pendingCheckpoint;
	extern CSyncChkptMessage checkpointMessage;
	extern CSyncChkptMessage checkpointMessagePending;
	extern CSyncCheckpoint invalidCheckpoint;
	extern CCriticalSection cs_hashSyncCheckpoint;
	extern CBlockIndex* GetLastSyncCheckpoint();
	extern bool ValidateSyncCheckpoint(CSyncCheckpoint hashCheckpoint);
	extern bool ReadSyncCheckpoint(CSyncCheckpoint& hashCheckpoint);
	extern bool WriteSyncCheckpoint(const CSyncCheckpoint& hashCheckpoint);
	extern bool AcceptPendingSyncCheckpoint();
	extern uint256 AutoSelectSyncCheckpoint();
	extern bool CheckSync(const uint256& hashBlock, const CBlockIndex* pindexPrev);
	extern bool IsSecuredBySyncCheckpoint(const uint256& hashBlock);
	extern bool WantedByPendingSyncCheckpoint(uint256 hashBlock);
	extern bool ResetSyncCheckpoint();
	extern void AskForPendingSyncCheckpoint(CNode* pfrom);
	extern bool SetCheckpointPrivKey(CKey privKey);
	extern bool SendSyncCheckpoint(uint256 hashCheckpoint, const CSyncChkParams &syncChkParamsOut);
	extern bool IsSyncCheckpointTooOld(unsigned int nSeconds);
	extern bool ReadCheckpointPubKey(std::string& strPubKeysOut);
	extern bool WriteCheckpointPubKey(const std::string& strPubKeys);
}

class CUnsignedSyncChkptMessage
{
public:
	int nVersion;
	uint256 hashCheckpoint;      // checkpoint block

	ADD_SERIALIZE_METHODS;
	template <typename Stream, typename Operation>
	inline void SerializationOp(Stream& s, Operation ser_action)
	{
		READWRITE(this->nVersion);
		READWRITE(hashCheckpoint);
	}
	void SetNull();
	std::string ToString() const;
	void print() const;
};

class CSyncChkptMessage : public CUnsignedSyncChkptMessage
{
public:
	static CKey masterKey;

	std::vector<unsigned char> vchMsg;
	std::vector<unsigned char> vchSig;

	CSyncChkptMessage();
	ADD_SERIALIZE_METHODS;
	template <typename Stream, typename Operation>
	inline void SerializationOp(Stream& s, Operation ser_action)
	{
		READWRITE(vchMsg);
		READWRITE(vchSig);
	}
	void SetNull();
	bool IsNull() const;
	uint256 GetHash() const;
	bool RelayTo(CNode* pnode) const;
	bool CheckSignature(const std::string &sPubkey);
	bool ProcessSyncCheckpoint(CNode* pfrom, const std::string &sPubkey, std::string &sReasonOut);
	static CPubKey ParseMasterPubkey(const std::string &sPubkey);
};

// Komodo added
namespace Checkpoints
{
	extern bool TryInitSyncCheckpoint(const CSyncChkParams &syncChkParams);
	extern bool OpenSyncCheckpointAtStartup(const CSyncChkParams &syncChkParams);
	extern bool IsMasterKeySet();
	extern void TryInitMasterKey();
	extern bool IsSyncCheckpointUpgradeActive(CSyncChkParams &syncChkParamsOut, int nHeight, int64_t timestamp);
	extern bool IsSyncCheckpointUpgradeActive(int nHeight, int64_t timestamp);
}

#endif
