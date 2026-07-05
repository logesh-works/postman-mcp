package com.acme;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/payments")
public class PaymentController {

    @PostMapping
    public PaymentResponse create(@RequestBody PaymentRequest request) {
        return new PaymentResponse();
    }

    @GetMapping("/{id}")
    public PaymentResponse get(@PathVariable String id) {
        return new PaymentResponse();
    }

    @DeleteMapping("/{id}")
    public void refund(@PathVariable String id) {
    }
}
