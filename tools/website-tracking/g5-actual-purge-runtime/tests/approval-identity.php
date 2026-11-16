<?php
declare(strict_types=1);
namespace BSRE\PurgeNative;

/** Fixture identity only: object key order is irrelevant; keys, values and types are exact. */
final class ApprovalIdentity {
    private const FIELDS=['action','actor','approval_expires_at','approved_at','plan_digest'];
    public static function same(mixed $candidate,mixed $known):bool {
        if(!is_array($candidate)||!is_array($known))return false;
        $left=array_keys($candidate);$right=array_keys($known);sort($left,SORT_STRING);sort($right,SORT_STRING);
        if($left!==self::FIELDS||$right!==self::FIELDS)return false;
        foreach(['approved_at','approval_expires_at'] as $field)if(!is_int($known[$field])||$known[$field]<=0)return false;
        if(!is_string($known['actor'])||preg_match('/^wp-user:[1-9][0-9]*$/D',$known['actor'])!==1)return false;
        if(!is_string($known['action'])||$known['action']===''||!is_string($known['plan_digest'])||preg_match('/^[a-f0-9]{64}$/D',$known['plan_digest'])!==1)return false;
        foreach(self::FIELDS as $field)if($candidate[$field]!==$known[$field])return false;
        return true;
    }
}
