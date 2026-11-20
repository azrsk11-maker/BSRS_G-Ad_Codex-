<?php
declare(strict_types=1);
namespace BSRE\ClosedRetention;

// Pure contract tests do not load WordPress. Real SQL custody requires this dedicated connection.
if (class_exists('\wpdb')) {
    final class LeaseBoundWpdb extends \wpdb
    {
        private bool $custodyActive = false;
        private ?string $custodyConnection = null;

        public function beginCustody(): void
        {
            if ($this->custodyActive) throw new Failure('CLOSURE_LEASE_BUSY');
            $this->custodyActive = true;
            try {
                $this->custodyConnection = $this->rawConnectionId();
            } catch (\Throwable $error) {
                throw new Failure('RETIREMENT_CONNECTION_LEASE_LOST');
            }
        }
        public function endCustody(): void
        {
            $this->custodyActive = false;
            $this->custodyConnection = null;
        }
        public function custodyConnectionId(): ?string { return $this->custodyConnection; }
        public function custodyIsActive(): bool { return $this->custodyActive; }

        public function query($query)
        {
            if ($this->custodyActive) {
                try { $current = $this->rawConnectionId(); }
                catch (\Throwable $error) { throw new Failure('RETIREMENT_CONNECTION_LEASE_LOST'); }
                if ($current !== $this->custodyConnection) throw new Failure('RETIREMENT_CONNECTION_LEASE_LOST');
            }
            return parent::query($query);
        }
        public function check_connection($allow_bail = true)
        {
            if ($this->custodyActive) return false;
            return parent::check_connection($allow_bail);
        }
        public function db_connect($allow_bail = true)
        {
            if ($this->custodyActive) return false;
            return parent::db_connect($allow_bail);
        }
        private function rawConnectionId(): string
        {
            if (!($this->dbh instanceof \mysqli)) throw new Failure('RETIREMENT_CONNECTION_LEASE_LOST');
            $result = @mysqli_query($this->dbh, 'SELECT CONNECTION_ID()');
            if (!($result instanceof \mysqli_result)) throw new Failure('RETIREMENT_CONNECTION_LEASE_LOST');
            try { $row = mysqli_fetch_row($result); }
            finally { mysqli_free_result($result); }
            if (!is_array($row) || !isset($row[0]) || !preg_match('/^[1-9][0-9]*$/D', (string) $row[0])) throw new Failure('RETIREMENT_CONNECTION_LEASE_LOST');
            return (string) $row[0];
        }
    }
}
