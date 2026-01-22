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

// Sync checkpoint activation params for asset chains

#include <map>
#include <vector>
#include <string>
#include "key.h"
#include "key_io.h"
#include "main.h"
#include "auto_checkpoints.h"
#include "komodo_hardfork.h"
#include "komodo_bitcoind.h" 

using namespace std;

namespace Checkpoints
{
    struct CSyncCheckpointActivation {
        map<string, CSyncChkParams> asset_chains;
        boost::optional<CSyncChkParams> mainnet_params;
        boost::optional<CSyncChkParams> testnet_params;

        // TODO: fix master key
        CSyncCheckpointActivation() {
            mainnet_params = CSyncChkParams { nSyncChkPointHeight, "03fdc6ca526c0cfaed2211d03dc2ea9c083aea127c7769d97dc92fed2085803ce3" };
            testnet_params = boost::none;

            asset_chains = {
                { "CCL", { nSyncChkPointTimestamp, "03fdc6ca526c0cfaed2211d03dc2ea9c083aea127c7769d97dc92fed2085803ce3" }},
                { "CLC", { nSyncChkPointTimestamp, "03fdc6ca526c0cfaed2211d03dc2ea9c083aea127c7769d97dc92fed2085803ce3" }},
                { "GLEEC", { nSyncChkPointTimestamp, "03fdc6ca526c0cfaed2211d03dc2ea9c083aea127c7769d97dc92fed2085803ce3" }},
                // { "ILN", { nSyncChkPointTimestamp, "03fdc6ca526c0cfaed2211d03dc2ea9c083aea127c7769d97dc92fed2085803ce3" }},
                // { "KOIN", { nSyncChkPointTimestamp, "03fdc6ca526c0cfaed2211d03dc2ea9c083aea127c7769d97dc92fed2085803ce3" }},
                // { "PIRATE", { nSyncChkPointTimestamp, "03fdc6ca526c0cfaed2211d03dc2ea9c083aea127c7769d97dc92fed2085803ce3" }},
                { "THC", { nSyncChkPointTimestamp, "03fdc6ca526c0cfaed2211d03dc2ea9c083aea127c7769d97dc92fed2085803ce3" }},
                { "BCZERO", { nBczeroRaphMdxSyncCheckpointTimestamp, "03fdc6ca526c0cfaed2211d03dc2ea9c083aea127c7769d97dc92fed2085803ce3" }},
                { "RAPH", { nBczeroRaphMdxSyncCheckpointTimestamp, "03fdc6ca526c0cfaed2211d03dc2ea9c083aea127c7769d97dc92fed2085803ce3" }},
                { "MDX", { nBczeroRaphMdxSyncCheckpointTimestamp, "03fdc6ca526c0cfaed2211d03dc2ea9c083aea127c7769d97dc92fed2085803ce3" }},

                // test chains:
                { "DOC", { nSyncChkPointTimestamp, "03fdc6ca526c0cfaed2211d03dc2ea9c083aea127c7769d97dc92fed2085803ce3" }},
                { "MARTY", { nSyncChkPointTimestamp, "03fdc6ca526c0cfaed2211d03dc2ea9c083aea127c7769d97dc92fed2085803ce3" }},
                // add more asset chains
                
                // test chain
                // auto checkpoint active since Dec, 01 2025
                { "GULDEN", { 1764606619, "02f9dc5271cc789aab77fb27e8007e681f93135cfcf92d4a514a4649c0e36f14ad" }}

            };
        }

        static bool GetAssetParams(const string &chain, CSyncChkParams &syncChkParams);
        static bool GetMainnetParams(CSyncChkParams &syncChkParams);
        static bool GetTestnetParams(CSyncChkParams &syncChkParams);
        static bool GetChainParams(CSyncChkParams &syncChkParams);
    };

    static CSyncCheckpointActivation syncChkActivation;

    bool CSyncCheckpointActivation::GetAssetParams(const string &chain, CSyncChkParams &syncChkParamsOut)
    {
        if (syncChkActivation.asset_chains.find(chain) != syncChkActivation.asset_chains.end()) {
            syncChkParamsOut = syncChkActivation.asset_chains[chain];
            return true;
        }
        return false;
    }
    bool CSyncCheckpointActivation::GetMainnetParams(CSyncChkParams &syncChkParamsOut)
    {
        if (syncChkActivation.mainnet_params) {
            syncChkParamsOut = *syncChkActivation.mainnet_params;
            return true;
        }
        return false;
    }
    bool CSyncCheckpointActivation::GetTestnetParams(CSyncChkParams &syncChkParamsOut)
    {
        if (syncChkActivation.testnet_params) {
            syncChkParamsOut = *syncChkActivation.testnet_params;
            return true;
        }
        return false;
    }

    bool CSyncCheckpointActivation::GetChainParams(CSyncChkParams &syncChkParamsOut)
    {
        if (chainName.ToString().empty()) {
            LogPrintf("CSyncCheckpointActivation::GetChainParams: chainName not initialised yet\n");
            return false;
        }
        if (chainName.isKMD()) {
            if (GetBoolArg("-testnet", false)) {
                if (!CSyncCheckpointActivation::GetTestnetParams(syncChkParamsOut)) {
                    return false;
                }
            } else {
                if (!CSyncCheckpointActivation::GetMainnetParams(syncChkParamsOut)) {
                    return false;
                }
            }
        } else if (!CSyncCheckpointActivation::GetAssetParams(chainName.ToString(), syncChkParamsOut)) {
            LogPrint("chk", "CSyncCheckpointActivation::GetChainParams: GetAssetParams returned false, chainName=%s\n", chainName.ToString());
            return false;
        }
        return true;
    }


    // Is Gulden sync checkpoints active for this chain and height or timestamp
    static bool GetSyncCheckpointActivationParams(CSyncChkParams &syncChkParamsOut, int nHeight, int64_t timestamp) {
        AssertLockHeld(cs_main);
        if (!CSyncCheckpointActivation::GetChainParams(syncChkParamsOut))
            return false;

        if (syncChkParamsOut.activeAt < LOCKTIME_THRESHOLD) { // height or timestamp
            if (nHeight > syncChkParamsOut.activeAt) { // same 'greater' comparison as for komodo seasons
                LogPrint("chk", "%s: nHeight %d > syncChkParams.activeAt %lld sync checkpoint is active\n", __func__, nHeight, syncChkParamsOut.activeAt);
                return true;
            }
        } else {
            if (timestamp > syncChkParamsOut.activeAt) { // same 'greater' comparison as for komodo seasons
                LogPrint("chk", "%s: timestamp %lld > syncChkParams.activeAt %lld sync checkpoint is active\n", __func__, timestamp, syncChkParamsOut.activeAt);
                return true;
            }
        }
        return false;
    }

    bool IsSyncCheckpointUpgradeActive(CSyncChkParams &syncChkParamsOut, int nHeight, int64_t timestamp) {
        return GetSyncCheckpointActivationParams(syncChkParamsOut, nHeight, timestamp);
    }
    bool IsSyncCheckpointUpgradeActive(int nHeight, int64_t timestamp) {
        CSyncChkParams syncChkParamsOut;
        return GetSyncCheckpointActivationParams(syncChkParamsOut, nHeight, timestamp);
    }

    // Try to find the private key for the master pubkey in the wallet
    void TryInitMasterKey()
    {
        if (!IsMasterKeySet()) {
            CSyncChkParams syncChkParams;

            if (!CSyncCheckpointActivation::GetChainParams(syncChkParams))
                return;
            if (pwalletMain) {
                LOCK(pwalletMain->cs_wallet);
                CPubKey pubkey(ParseHex(syncChkParams.masterPubKey));
                CKey privkey;
                if (pwalletMain->GetKey(pubkey.GetID(), privkey)) {
                    if (SetCheckpointPrivKey(privkey)) {
                        LogPrintf("%s: Sync checkpoint master key set for pubkey %s\n", __func__, syncChkParams.masterPubKey);
                    }
                }
            }
        }
    }


    // Try to init checkpoint DB if upgrade activated after loading block index
    // and get master key from wallet
    bool TryInitSyncCheckpoint(const CSyncChkParams &syncChkParams) 
    {    
        LOCK(cs_hashSyncCheckpoint);
        if (!fTryInitDone) {
            if (!Checkpoints::WriteCheckpointPubKey(syncChkParams.masterPubKey)) {
                return error("%s: failed to write new checkpoint master key", __func__);  
            }
            LogPrintf("%s: sync checkpoint try init done\n", __func__);
            TryInitMasterKey();
            fTryInitDone = true;
        }
        return true;
    }

    // Read sync checkpoint on startup.
    // As wallet is not ready yet we will get master key later, when a new checkpoint is created or received first time 
    bool OpenSyncCheckpointAtStartup(const CSyncChkParams &syncChkParams) 
    {
        LOCK(cs_hashSyncCheckpoint);
        // Gulden: load hashSyncCheckpoint (must be in db already)
        if (!Checkpoints::ReadSyncCheckpoint(Checkpoints::syncCheckpoint)) {
            Checkpoints::CSyncCheckpoint genesisCheckpoint { Params().GenesisBlock().GetHash() };
            if (!Checkpoints::WriteSyncCheckpoint(genesisCheckpoint)) {
                return error("%s: failed to init sync checkpoint file", __func__);
            }
            if (!Checkpoints::ReadSyncCheckpoint(Checkpoints::syncCheckpoint)) {
                return error("%s: failed to read sync checkpoint file", __func__);  
            }    
        }

        if (mapBlockIndex.count(syncCheckpoint.GetHash()) == 0) {
            return error("%s: sync checkpoint file corrupted. Remove sync checkpoint dir and restart", __func__);  
        }
        LogPrintf("%s: using synchronized checkpoint %s\n", __func__, Checkpoints::syncCheckpoint.ToString());

        std::string strPubKey;
        if (!Checkpoints::ReadCheckpointPubKey(strPubKey) || strPubKey != syncChkParams.masterPubKey) {
            LogPrintf("%s: pubKey from file: %s\n", __func__, strPubKey);
            LogPrintf("%s: masterPubKey: %s\n", __func__, syncChkParams.masterPubKey);
            // write new checkpoint master keys to db
            if (!Checkpoints::WriteCheckpointPubKey(syncChkParams.masterPubKey)) {
                return error("%s: failed to write new checkpoint master key", __func__);
            }
            if (!Checkpoints::ResetSyncCheckpoint()) {
                return error("%s: failed to reset sync-checkpoint", __func__);
            }
        }
        return true;
    }
}