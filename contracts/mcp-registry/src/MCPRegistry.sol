// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title MCPRegistry — ERC-8004-inspired identity registry for MCP servers
contract MCPRegistry {
    struct CapabilityScore {
        uint16 dataScoreBps;      // 0-10000 (basis points)
        uint16 pathScoreBps;
        uint16 tokenEfficiencyBps;
        uint16 compositeBps;
        bool failed;
        string walrusBlobId;
    }

    struct MCPRecord {
        string name;
        string mcpEndpoint;
        string agentUri;
        string ensName;
        string lastAttestationId;
        bytes32 lastTranscriptHash;
        bool exists;
    }

    uint256 public nextAgentId = 1;
    mapping(uint256 => MCPRecord) public records;
    mapping(uint256 => mapping(string => CapabilityScore)) public capabilityScores;
    mapping(string => uint256) public nameToAgentId;

    event MCPRegistered(uint256 indexed agentId, string name, string endpoint);
    event ScoreUpdated(uint256 indexed agentId, string capability, uint16 compositeBps, bool failed);
    event AttestationRecorded(uint256 indexed agentId, string inferenceId, bytes32 transcriptHash);

    function register(
        string calldata name,
        string calldata mcpEndpoint,
        string calldata agentUri,
        string calldata ensName
    ) external returns (uint256 agentId) {
        require(bytes(name).length > 0, "name required");
        require(nameToAgentId[name] == 0, "name taken");

        agentId = nextAgentId++;
        records[agentId] = MCPRecord({
            name: name,
            mcpEndpoint: mcpEndpoint,
            agentUri: agentUri,
            ensName: ensName,
            lastAttestationId: "",
            lastTranscriptHash: bytes32(0),
            exists: true
        });
        nameToAgentId[name] = agentId;
        emit MCPRegistered(agentId, name, mcpEndpoint);
    }

    function updateCapabilityScore(
        uint256 agentId,
        string calldata capability,
        uint16 dataScoreBps,
        uint16 pathScoreBps,
        uint16 tokenEfficiencyBps,
        uint16 compositeBps,
        bool failed,
        string calldata walrusBlobId
    ) external {
        require(records[agentId].exists, "unknown agent");
        capabilityScores[agentId][capability] = CapabilityScore({
            dataScoreBps: dataScoreBps,
            pathScoreBps: pathScoreBps,
            tokenEfficiencyBps: tokenEfficiencyBps,
            compositeBps: compositeBps,
            failed: failed,
            walrusBlobId: walrusBlobId
        });
        emit ScoreUpdated(agentId, capability, compositeBps, failed);
    }

    function recordAttestation(
        uint256 agentId,
        string calldata inferenceId,
        bytes32 transcriptHash
    ) external {
        require(records[agentId].exists, "unknown agent");
        records[agentId].lastAttestationId = inferenceId;
        records[agentId].lastTranscriptHash = transcriptHash;
        emit AttestationRecorded(agentId, inferenceId, transcriptHash);
    }

    function getRecord(uint256 agentId) external view returns (MCPRecord memory) {
        require(records[agentId].exists, "unknown agent");
        return records[agentId];
    }

    function getCapabilityScore(
        uint256 agentId,
        string calldata capability
    ) external view returns (CapabilityScore memory) {
        require(records[agentId].exists, "unknown agent");
        return capabilityScores[agentId][capability];
    }
}
