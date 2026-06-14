// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice CRE KeystoneForwarder delivers a workflow report by calling onReport.
interface IReceiver {
    function onReport(bytes calldata metadata, bytes calldata report) external;
}

/// @title MCPRegistry — ERC-8004-inspired identity registry for MCP servers
contract MCPRegistry is IReceiver {
    /// Report kinds (first field of the ABI-encoded CRE report).
    uint8 internal constant KIND_SCORE = 1;
    uint8 internal constant KIND_ATTESTATION = 2;

    /// Trusted CRE forwarder allowed to call onReport (0 = onReport disabled).
    address public immutable forwarder;

    error UnauthorizedForwarder(address sender);
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

    /// @param forwarder_ CRE KeystoneForwarder (or MockKeystoneForwarder for simulate
    ///        --broadcast). Pass address(0) to disable the onReport path entirely.
    constructor(address forwarder_) {
        forwarder = forwarder_;
    }

    /// @notice ERC-165 — the KeystoneForwarder staticcalls this to confirm the
    ///         receiver supports IReceiver before delivering a report via onReport.
    function supportsInterface(bytes4 interfaceId) external pure returns (bool) {
        return
            interfaceId == 0x01ffc9a7 || // ERC-165
            interfaceId == IReceiver.onReport.selector; // IReceiver (single-method)
    }

    /// @inheritdoc IReceiver
    /// @dev The report is `abi.encode(uint8 kind, ...)`. kind=1 score, kind=2 attestation.
    ///      Matches the workflow's encodeAbiParameters in writeScoreToArc/writeAttestationToArc.
    function onReport(bytes calldata, bytes calldata report) external {
        if (msg.sender != forwarder) revert UnauthorizedForwarder(msg.sender);
        uint8 kind = abi.decode(report, (uint8));
        if (kind == KIND_SCORE) {
            (
                ,
                uint256 agentId,
                string memory capability,
                uint16 dataScoreBps,
                uint16 pathScoreBps,
                uint16 tokenEfficiencyBps,
                uint16 compositeBps,
                bool failed,
                string memory walrusBlobId
            ) = abi.decode(
                report,
                (uint8, uint256, string, uint16, uint16, uint16, uint16, bool, string)
            );
            _updateCapabilityScore(
                agentId, capability, dataScoreBps, pathScoreBps, tokenEfficiencyBps, compositeBps, failed, walrusBlobId
            );
        } else if (kind == KIND_ATTESTATION) {
            (, uint256 agentId, string memory inferenceId, bytes32 transcriptHash) =
                abi.decode(report, (uint8, uint256, string, bytes32));
            _recordAttestation(agentId, inferenceId, transcriptHash);
        } else {
            revert("unknown report kind");
        }
    }

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
        _updateCapabilityScore(
            agentId, capability, dataScoreBps, pathScoreBps, tokenEfficiencyBps, compositeBps, failed, walrusBlobId
        );
    }

    function _updateCapabilityScore(
        uint256 agentId,
        string memory capability,
        uint16 dataScoreBps,
        uint16 pathScoreBps,
        uint16 tokenEfficiencyBps,
        uint16 compositeBps,
        bool failed,
        string memory walrusBlobId
    ) internal {
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
        _recordAttestation(agentId, inferenceId, transcriptHash);
    }

    function _recordAttestation(
        uint256 agentId,
        string memory inferenceId,
        bytes32 transcriptHash
    ) internal {
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
