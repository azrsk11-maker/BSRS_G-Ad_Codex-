<?php
declare(strict_types=1);
require_once __DIR__ . '/Workflow.php';
use BSRE\ClosedRetention as C;

/** Synthetic local-pipe receiver adapter only. No network, OAuth or production credentials. */
final class SyntheticReceiverPipe implements C\NoMailRetirement
{
    private $process;
    private array $pipes = [];
    public $alterProof = null;
    public bool $loseForgetAcknowledgement = false;
    public bool $loseRetirementAcknowledgement = false;
    public function __construct()
    {
        if (!defined('BSRE_CLOSED_RETENTION_LAB') || BSRE_CLOSED_RETENTION_LAB !== true
            || !function_exists('wp_get_environment_type') || wp_get_environment_type() !== 'local'
            || !function_exists('home_url') || home_url() !== 'http://bsre.invalid') throw new C\Failure('ISOLATED_LAB_ONLY');
        $this->process = proc_open(['node', __DIR__ . '/receiver-fence/bridge.mjs'],
            [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $this->pipes, __DIR__);
        if (!is_resource($this->process)) throw new RuntimeException('Synthetic source bridge unavailable');
        stream_set_timeout($this->pipes[1], 5);
    }
    public function call(string $action, array $arguments = [])
    {
        $wire = json_encode(['action' => $action] + $arguments, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES) . "\n";
        if (fwrite($this->pipes[0], $wire) !== strlen($wire)) throw new RuntimeException('Synthetic bridge write failed');
        fflush($this->pipes[0]);
        $line = fgets($this->pipes[1], 32769);
        if ($line === false || !str_ends_with($line, "\n")) throw new RuntimeException('Synthetic bridge response unavailable');
        $result = json_decode($line, true, 32, JSON_THROW_ON_ERROR);
        if ($result['ok'] !== true) throw new C\Failure($result['error']);
        return $result['value'];
    }
    public function readback(array $scope, int $now, bool $cleanup = false, ?array $ticket = null): ?array
    {
        $value = $this->call('readback', compact('scope', 'now', 'cleanup', 'ticket'));
        return $this->alterProof ? ($this->alterProof)($value) : $value;
    }
    public $beforeOwnerSource = null;
    public function inspect(array $scope, int $now): ?array
    {
        if ($this->beforeOwnerSource) ($this->beforeOwnerSource)('inspect', $scope);
        return $this->call('inspect_retirement', compact('scope', 'now'));
    }
    public function retire(array $scope, array $record, int $now): ?array
    {
        C\RetirementIntent::validateRecord($record, $now);
        if (C\Workflow::digest($scope) !== C\Workflow::digest($record['plan']['scope'])) throw new C\Failure('RETIREMENT_SCOPE_INVALID');
        if ($this->beforeOwnerSource) ($this->beforeOwnerSource)('retire', $scope);
        $this->call('authorize_retirement', ['claim' => C\RetirementIntent::authorization($record)]);
        $proof = $this->call('retire_authorized', ['scope' => $scope, 'intent_digest' => $record['plan']['digest'], 'now' => $now]);
        if ($this->loseRetirementAcknowledgement) {
            $this->loseRetirementAcknowledgement = false;
            throw new C\Failure('RETIREMENT_SOURCE_ACK_UNCERTAIN');
        }
        return $proof;
    }
    public function prepareCleanup(array $scope, int $now): ?array { return $this->call('prepare_cleanup', compact('scope', 'now')); }
    public function forget(array $scope, int $now, array $ticket): bool
    {
        $value = $this->call('forget', compact('scope', 'now', 'ticket'));
        if ($this->loseForgetAcknowledgement) {
            $this->loseForgetAcknowledgement = false;
            throw new C\Failure('NO_COPY_CUSTODY_UNCONFIRMED');
        }
        return $value;
    }
    public function __destruct()
    {
        foreach ($this->pipes as $pipe) if (is_resource($pipe)) fclose($pipe);
        if (is_resource($this->process)) proc_close($this->process);
    }
}
