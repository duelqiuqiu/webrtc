/*
 *  Copyright (c) 2015 The WebRTC project authors. All Rights Reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#include "webrtc/modules/audio_coding/neteq/tools/rtc_event_log_source.h"

#include <assert.h>
#include <string.h>
#include <iostream>
#include <limits>

#include "webrtc/base/checks.h"
#include "webrtc/modules/audio_coding/neteq/tools/packet.h"
#include "webrtc/modules/rtp_rtcp/interface/rtp_header_parser.h"
#include "webrtc/video/rtc_event_log.h"

// Files generated at build-time by the protobuf compiler.
#ifdef WEBRTC_ANDROID_PLATFORM_BUILD
#include "external/webrtc/webrtc/video/rtc_event_log.pb.h"
#else
#include "webrtc/video/rtc_event_log.pb.h"
#endif

namespace webrtc {
namespace test {

namespace {

const rtclog::RtpPacket* GetRtpPacket(const rtclog::Event& event) {
  if (!event.has_type() || event.type() != rtclog::Event::RTP_EVENT)
    return nullptr;
  if (!event.has_timestamp_us() || !event.has_rtp_packet())
    return nullptr;
  const rtclog::RtpPacket& rtp_packet = event.rtp_packet();
  if (!rtp_packet.has_type() || rtp_packet.type() != rtclog::AUDIO ||
      !rtp_packet.has_incoming() || !rtp_packet.incoming() ||
      !rtp_packet.has_packet_length() || rtp_packet.packet_length() == 0 ||
      !rtp_packet.has_header() || rtp_packet.header().size() == 0 ||
      rtp_packet.packet_length() < rtp_packet.header().size())
    return nullptr;
  return &rtp_packet;
}

const rtclog::DebugEvent* GetAudioOutputEvent(const rtclog::Event& event) {
  if (!event.has_type() || event.type() != rtclog::Event::DEBUG_EVENT)
    return nullptr;
  if (!event.has_timestamp_us() || !event.has_debug_event())
    return nullptr;
  const rtclog::DebugEvent& debug_event = event.debug_event();
  if (!debug_event.has_type() ||
      debug_event.type() != rtclog::DebugEvent::AUDIO_PLAYOUT)
    return nullptr;
  return &debug_event;
}

}  // namespace

RtcEventLogSource* RtcEventLogSource::Create(const std::string& file_name) {
  RtcEventLogSource* source = new RtcEventLogSource();
  CHECK(source->OpenFile(file_name));
  return source;
}

RtcEventLogSource::~RtcEventLogSource() {}

bool RtcEventLogSource::RegisterRtpHeaderExtension(RTPExtensionType type,
                                                   uint8_t id) {
  CHECK(parser_.get());
  return parser_->RegisterRtpHeaderExtension(type, id);
}

Packet* RtcEventLogSource::NextPacket() {
  while (rtp_packet_index_ < event_log_->stream_size()) {
    const rtclog::Event& event = event_log_->stream(rtp_packet_index_);
    const rtclog::RtpPacket* rtp_packet = GetRtpPacket(event);
    rtp_packet_index_++;
    if (rtp_packet) {
      uint8_t* packet_header = new uint8_t[rtp_packet->header().size()];
      memcpy(packet_header, rtp_packet->header().data(),
             rtp_packet->header().size());
      Packet* packet = new Packet(packet_header, rtp_packet->header().size(),
                                  rtp_packet->packet_length(),
                                  event.timestamp_us() / 1000, *parser_.get());
      if (packet->valid_header()) {
        // Check if the packet should not be filtered out.
        if (!filter_.test(packet->header().payloadType) &&
            !(use_ssrc_filter_ && packet->header().ssrc != ssrc_))
          return packet;
      } else {
        std::cout << "Warning: Packet with index " << (rtp_packet_index_ - 1)
                  << " has an invalid header and will be ignored." << std::endl;
      }
      // The packet has either an invalid header or needs to be filtered out, so
      // it can be deleted.
      delete packet;
    }
  }
  return nullptr;
}

int64_t RtcEventLogSource::NextAudioOutputEventMs() {
  while (audio_output_index_ < event_log_->stream_size()) {
    const rtclog::Event& event = event_log_->stream(audio_output_index_);
    const rtclog::DebugEvent* debug_event = GetAudioOutputEvent(event);
    audio_output_index_++;
    if (debug_event)
      return event.timestamp_us() / 1000;
  }
  return std::numeric_limits<int64_t>::max();
}

RtcEventLogSource::RtcEventLogSource()
    : PacketSource(), parser_(RtpHeaderParser::Create()) {}

bool RtcEventLogSource::OpenFile(const std::string& file_name) {
  event_log_.reset(new rtclog::EventStream());
  return RtcEventLog::ParseRtcEventLog(file_name, event_log_.get());
}

}  // namespace test
}  // namespace webrtc
